# import_credits_to_users.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import asyncio, os, sys, logging, re, uuid
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from passlib.hash import bcrypt  # تأكد من تثبيته: pip install passlib[bcrypt]
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("CreditsImporter")

load_dotenv()

def get_db_url():
    db_url = os.getenv("DATABASE_URL")
    if not db_url: sys.exit("DATABASE_URL missing")
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    parsed = urlparse(db_url)
    params = parse_qs(parsed.query)
    params.pop('channel_binding', None); params.pop('sslmode', None)
    params['ssl'] = ['require']
    new_qs = urlencode(params, doseq=True)
    return urlunparse(parsed._replace(query=new_qs))

def clean_number(v):
    if pd.isna(v) or v == '' or v is None: return 0.0
    n = re.sub(r'[^\d.]', '', str(v))
    return float(n) if n else 0.0

async def import_credits(csv_path):
    df = pd.read_csv(csv_path)
    logger.info(f"Loaded {len(df)} credit profiles.")
    engine = create_async_engine(get_db_url(), echo=False)

    async with engine.begin() as conn:
        for idx, row in df.iterrows():
            email = f"credit_user_{idx}@example.com"
            hashed_pwd = bcrypt.hash("password123")  # كلمة مرور افتراضية
            full_name = f"Credit User {idx}"
            role = "CLIENT"
            monthly_income = clean_number(row.get('income', 0)) / 12  # إذا كان الدخل سنويًا
            credit_score = int(row.get('credit_score', 0))
            employment = str(row.get('employment_status', '')).strip()
            external_url = f"credit_import_{idx}"

            # تحقق من وجود المستخدم
            check = await conn.execute(text("SELECT id FROM users WHERE external_url = :url"), {"url": external_url})
            if check.fetchone():
                continue

            # إدراج المستخدم
            await conn.execute(text("""
                INSERT INTO users (email, hashed_password, full_name, role, monthly_income, credit_score, employment_status, external_url)
                VALUES (:email, :pwd, :name, :role, :income, :score, :emp, :url)
            """), {"email": email, "pwd": hashed_pwd, "name": full_name, "role": role,
                  "income": monthly_income, "score": credit_score, "emp": employment, "url": external_url})

    await engine.dispose()
    logger.info("Credit profiles imported to users table.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python import_credits_to_users.py credits.csv")
        sys.exit(1)
    asyncio.run(import_credits(sys.argv[1]))