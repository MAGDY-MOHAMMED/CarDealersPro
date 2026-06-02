# generate_parquet.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import asyncio
import os

import logging
import re  
from pathlib import Path
import pandas as pd
import numpy as np
import pyarrow.parquet as pq
import pyarrow as pa
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import select, text
from dotenv import load_dotenv
from app.models import Car
from app.core.config import settings
from sklearn.preprocessing import LabelEncoder, StandardScaler
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("ParquetGen")

def get_db_url() -> str:
    """ترجع URL صالح لـ asyncpg بعد تنظيف المعاملات غير المدعومة"""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        # fallback للإعدادات المحلية (للاستخدام في التطوير)
        db_url = (
            f"postgresql+asyncpg://{settings.DATABASE_USERNAME}:{settings.DATABASE_PASSWORD}"
            f"@{settings.DATABASE_HOSTNAME}:{settings.DATABASE_PORT}/{settings.DATABASE_NAME}"
        )
        return db_url + "?ssl=require"  # لو قاعدة بيانات محلية مش محتاجة ssl، امسح السطر ده

    # تحويل رابط Neon/Local لـ asyncpg
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    # تحليل الرابط وتنقيته من channel_binding و sslmode
    parsed = urlparse(db_url)
    query_params = parse_qs(parsed.query)
    query_params.pop('channel_binding', None)
    query_params.pop('sslmode', None)
    # إضافة ssl=require (اللي بيفهمه asyncpg)
    query_params['ssl'] = ['require']
    new_query = urlencode(query_params, doseq=True)
    new_parsed = parsed._replace(query=new_query)
    return urlunparse(new_parsed)

async def generate():
    logger.info(f"Using DB URL: {get_db_url()}")
    engine = create_async_engine(get_db_url(), echo=False)

    # التحقق من وجود عمود mileage في جدول cars (إن لم يوجد، أضفه)
    async with engine.begin() as conn:
        cols = await conn.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name='cars'
        """))
        existing = [row[0] for row in cols]
        if 'mileage' not in existing:
            await conn.execute(text("ALTER TABLE cars ADD COLUMN IF NOT EXISTS mileage INTEGER DEFAULT 0"))
            logger.info("Added mileage column")

    async with AsyncSession(engine) as session:
        result = await session.execute(select(Car))
        cars = result.scalars().all()

    if not cars:
        logger.warning("No cars found!")
        await engine.dispose()
        return

    data = []
    for car in cars:
        data.append({
            "car_id": str(car.id),
            "brand": car.brand,
            "model": car.model,
            "year": car.year,
            "price_consumer": car.price_consumer,
            "mileage": getattr(car, "mileage", 0) or 0,
            "fuel_type": getattr(car, "fuel_type", "unknown") or "unknown",
            "transmission": getattr(car, "transmission", "unknown") or "unknown",
            "body_type": getattr(car, "body_type", "unknown") or "unknown",
        })
    df = pd.DataFrame(data)
    logger.info(f"Loaded {len(df)} cars from database.")

    # معالجة القيم المفقودة
    df['mileage'] = df['mileage'].fillna(0)
    df['fuel_type'] = df['fuel_type'].fillna('unknown')
    df['transmission'] = df['transmission'].fillna('unknown')
    df['body_type'] = df['body_type'].fillna('unknown')

    # تحويل النصوص لأرقام
    encoders = {
        'brand': LabelEncoder(),
        'model': LabelEncoder(),
        'fuel_type': LabelEncoder(),
        'transmission': LabelEncoder(),
        'body_type': LabelEncoder(),
    }
    for col, le in encoders.items():
        df[col + '_enc'] = le.fit_transform(df[col].astype(str))

    feature_cols = ['year', 'mileage', 'brand_enc', 'model_enc', 'fuel_type_enc', 'transmission_enc', 'body_type_enc']
    X = df[feature_cols].values.astype(float)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    features_list = X_scaled.tolist()

    # إعداد الـ DataFrame النهائي
    final_df = pd.DataFrame({
        "car_id": df["car_id"],
        "features": features_list,
        "price_prediction": df["price_consumer"].values,
        "damage_score": np.zeros(len(df))
    })

    output_dir = Path("data/optimized/")
    output_dir.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(final_df)
    pq.write_table(table, output_dir / "car_features.parquet")
    # print the path
    logger.info(f"Parquet written to {output_dir / 'car_features.parquet'} with {len(final_df)} rows.")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(generate())