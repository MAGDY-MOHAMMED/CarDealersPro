# import_table.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import asyncio
import os
import sys
import logging
import re
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("TableImporter")

load_dotenv()

def get_db_url() -> str:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL not found! Set it in .env")
        sys.exit(1)
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    parsed = urlparse(db_url)
    query_params = parse_qs(parsed.query)
    query_params.pop('channel_binding', None)
    query_params.pop('sslmode', None)
    query_params['ssl'] = ['require']
    new_query = urlencode(query_params, doseq=True)
    new_parsed = parsed._replace(query=new_query)
    return urlunparse(new_parsed)

def clean_number(value):
    if pd.isna(value) or value == '' or value is None:
        return 0.0
    cleaned = re.sub(r'[^\d.]', '', str(value))
    return float(cleaned) if cleaned else 0.0

async def get_existing_columns(engine, table_name: str):
    query = text("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = :tname
        ORDER BY ordinal_position;
    """)
    async with engine.connect() as conn:
        result = await conn.execute(query, {"tname": table_name})
        return [row[0] for row in result]

async def add_missing_column(conn, col_name: str, sample_value):
    if col_name in ("owner_id", "id", "uuid"):
        return
    if isinstance(sample_value, bool):
        col_type = "BOOLEAN"
    elif isinstance(sample_value, int):
        col_type = "INTEGER"
    elif isinstance(sample_value, float):
        col_type = "FLOAT"
    elif sample_value is None:
        col_type = "VARCHAR"
    else:
        col_type = "VARCHAR"
    sql = f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {col_name} {col_type}"
    if sample_value is not None and not isinstance(sample_value, (int, float, bool)):
        safe_val = str(sample_value).replace("'", "''")
        sql += f" DEFAULT '{safe_val}'"
    await conn.execute(text(sql))

async def import_csv_to_table(csv_path: str, table_name: str, id_prefix: str = "csv_import"):
    """
    استيراد ملف CSV إلى جدول معين.
    csv_path: مسار الملف
    table_name: اسم الجدول في قاعدة البيانات (مثلاً 'users', 'loan_applications')
    id_prefix: بادئة للرابط الفريد لمنع التكرار (مثلاً 'credit_import_')
    """
    logger.info(f"Importing {csv_path} into table '{table_name}'...")
    df = pd.read_csv(csv_path)
    logger.info(f"Loaded {len(df)} rows. Columns: {df.columns.tolist()}")

    engine = create_async_engine(get_db_url(), echo=False)
    existing_cols = await get_existing_columns(engine, table_name)
    logger.info(f"Existing columns in '{table_name}': {existing_cols}")

    # تأكد من وجود عمود external_url (أو id) لاستخدامه في تفادي التكرار
    if 'external_url' not in existing_cols:
        await add_missing_column(engine, 'external_url', '')
        existing_cols.append('external_url')

    total_inserted = 0
    async with engine.begin() as conn:
        for idx, row in df.iterrows():
            # تحويل الصف إلى قاموس. سنأخذ الأعمدة كما هي إن تطابقت أسماؤها مع أعمدة الجدول.
            record = {}
            for col in df.columns:
                val = row[col]
                # اسم العمود في CSV قد يختلف قليلاً، ننظفه
                col_name = col.strip().lower().replace(' ', '_')  # نجعل الأسماء حروف صغيرة وبدون مسافات
                # إذا كان العمود موجوداً في الجدول، نضيفه
                if col_name in existing_cols:
                    # معالجة الأنواع
                    if col_name in ('price', 'amount', 'income', 'price_consumer', 'price_dealer', 'monthly_income'):
                        record[col_name] = clean_number(val)
                    elif col_name in ('year', 'credit_score', 'tenure_months', 'mileage'):
                        try:
                            record[col_name] = int(float(val))
                        except (ValueError, TypeError):
                            record[col_name] = 0
                    else:
                        record[col_name] = str(val).strip() if pd.notna(val) else ''
                else:
                    # لو العمود مش موجود، نضيفه
                    if pd.notna(val):
                        await add_missing_column(conn, col_name, val)
                        existing_cols.append(col_name)
                        record[col_name] = str(val).strip() if isinstance(val, str) else val

            # إضافة حقل external_url لتفادي التكرار
            record['external_url'] = f"{id_prefix}_{idx}"

            # بناء جملة INSERT
            cols = list(record.keys())
            placeholders = ", ".join([f":{c}" for c in cols])
            insert_sql = f"INSERT INTO {table_name} ({', '.join(cols)}) VALUES ({placeholders}) ON CONFLICT (external_url) DO NOTHING"
            await conn.execute(text(insert_sql), record)
            total_inserted += 1
            if total_inserted % 100 == 0:
                logger.info(f"Inserted {total_inserted} rows into {table_name}...")

    await engine.dispose()
    logger.info(f"Import finished. Processed {len(df)} rows, new rows inserted: {total_inserted}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python import_table.py <csv_file> <table_name> [id_prefix]")
        sys.exit(1)
    csv_file = sys.argv[1]
    table = sys.argv[2]
    prefix = sys.argv[3] if len(sys.argv) > 3 else "csv_import"
    asyncio.run(import_csv_to_table(csv_file, table, prefix))