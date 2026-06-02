import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import os
import sys
import logging
import re
import uuid
import random
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import bcrypt as bcrypt_lib

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("MasterImporter")

load_dotenv()

# ================== إعدادات ==================
DB_URL_ENV = "DATABASE_URL"
CARS_CSV = "egyptian_cars.csv"
CREDITS_CSV = "credits.csv"
LOAN_COUNT = 500
BATCH_SIZE = 500  # عدد السجلات في كل دفعة

# ================== دوال مساعدة ==================
def get_db_url() -> str:
    db_url = os.getenv(DB_URL_ENV)
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

async def add_missing_column(conn, table_name: str, col_name: str, sample_value):
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

# ================== 1. استيراد السيارات (مع دفعات) ==================
async def import_cars(engine):
    logger.info("=== Importing Cars ===")
    if not os.path.exists(CARS_CSV):
        logger.warning(f"{CARS_CSV} not found, skipping cars import.")
        return
    df = pd.read_csv(CARS_CSV)
    logger.info(f"Loaded {len(df)} car rows.")

    required_cols = {
        "condition": "used", "external_url": "", "is_available": True,
        "is_deleted": False, "published": False, "price_dealer": 0.0,
    }

    async with engine.begin() as conn:
        existing = await conn.execute(text("""
            SELECT column_name FROM information_schema.columns WHERE table_name = 'cars'
        """))
        existing_cols = [row[0] for row in existing]
        for col, default_val in required_cols.items():
            if col not in existing_cols:
                await add_missing_column(conn, "cars", col, default_val)
                existing_cols.append(col)
        if "external_url" not in existing_cols:
            await conn.execute(text("ALTER TABLE cars ADD COLUMN IF NOT EXISTS external_url VARCHAR UNIQUE"))
            existing_cols.append("external_url")

    total = 0
    for batch_start in range(0, len(df), BATCH_SIZE):
        batch = df.iloc[batch_start:batch_start+BATCH_SIZE]
        success = False
        for attempt in range(5):
            try:
                async with engine.begin() as conn:
                    for idx, row in batch.iterrows():
                        actual_idx = batch_start + (idx - batch_start)
                        car_data = {
                            "brand": str(row.get("Brand", "")).strip() or "Unknown",
                            "model": str(row.get("Model", "")).strip() or "Unknown",
                            "year": int(float(row["Year"])) if pd.notna(row.get("Year")) else 2020,
                            "price_consumer": clean_number(row.get("Price_EGP")) if pd.notna(row.get("Price_EGP")) else 0.0,
                            "price_dealer": clean_number(row.get("Price_EGP")) if pd.notna(row.get("Price_EGP")) else 0.0,
                            "condition": "used",
                            "external_url": f"kaggle_car_{actual_idx}",
                            "owner_id": None,
                            "is_available": True,
                            "is_deleted": False,
                            "published": False,
                        }
                        km = row.get("Kilometers")
                        if pd.notna(km):
                            car_data["mileage"] = int(clean_number(km))
                        eng = row.get("Engine Capacity (CC)")
                        if pd.notna(eng):
                            car_data["engine_capacity"] = int(float(str(eng)))
                        for csv_col, db_col in {
                            "Fuel Type": "fuel_type",
                            "Transmission Type": "transmission",
                            "Body Type": "body_type"
                        }.items():
                            val = row.get(csv_col)
                            if pd.notna(val):
                                car_data[db_col] = str(val).strip()

                        cols = list(car_data.keys())
                        placeholders = ", ".join([f":{c}" for c in cols])
                        insert_sql = f"INSERT INTO cars ({', '.join(cols)}) VALUES ({placeholders}) ON CONFLICT (external_url) DO NOTHING"
                        await conn.execute(text(insert_sql), car_data)
                        total += 1
                success = True
                break
            except Exception as e:
                logger.warning(f"Batch {batch_start}-{batch_start+BATCH_SIZE} attempt {attempt+1} failed: {e}")
                await asyncio.sleep(2 ** attempt)
        if not success:
            logger.error(f"Failed to import batch {batch_start}-{batch_start+BATCH_SIZE} after 5 attempts")
        else:
            logger.info(f"Cars imported: {total}/{len(df)}")

    logger.info(f"Cars import done. Total: {total}")

# ================== 2. استيراد ملفات الائتمان (بدفعات) ==================
async def import_credits(engine):
    logger.info("=== Importing Credit Profiles as Users ===")
    if not os.path.exists(CREDITS_CSV):
        logger.warning(f"{CREDITS_CSV} not found, skipping credits import.")
        return
    df = pd.read_csv(CREDITS_CSV)
    logger.info(f"Loaded {len(df)} credit profiles.")

    async with engine.begin() as conn:
        existing = await conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='users'"))
        cols = [r[0] for r in existing]
        if "external_url" not in cols:
            await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS external_url VARCHAR UNIQUE"))

    total = 0
    for batch_start in range(0, len(df), BATCH_SIZE):
        batch = df.iloc[batch_start:batch_start+BATCH_SIZE]
        success = False
        for attempt in range(5):
            try:
                async with engine.begin() as conn:
                    for idx, row in batch.iterrows():
                        actual_idx = batch_start + (idx - batch_start)
                        email = f"credit_user_{actual_idx}@cardealerspro.com"
                        raw_pwd = "Secure123!"
                        hashed_pwd = bcrypt_lib.hashpw(raw_pwd.encode('utf-8'), bcrypt_lib.gensalt()).decode('utf-8')
                        full_name = f"Credit User {actual_idx}"
                        role = "CLIENT"
                        monthly_income = clean_number(row.get("income", 0)) / 12 if pd.notna(row.get("income")) else 5000
                        credit_score = int(row.get("credit_score", 0)) if pd.notna(row.get("credit_score")) else 600
                        employment = str(row.get("employment_status", "")).strip() or "Employed"
                        external_url = f"credit_import_{actual_idx}"

                        check = await conn.execute(text("SELECT id FROM users WHERE external_url = :u"), {"u": external_url})
                        if check.fetchone():
                            continue
                        await conn.execute(text("""
                            INSERT INTO users (email, hashed_password, full_name, role, monthly_income, credit_score, employment_status, external_url)
                            VALUES (:em, :pw, :nm, :rl, :inc, :cs, :emp, :url)
                        """), {"em": email, "pw": hashed_pwd, "nm": full_name, "rl": role,
                              "inc": monthly_income, "cs": credit_score, "emp": employment, "url": external_url})
                        total += 1
                success = True
                break
            except Exception as e:
                logger.warning(f"Credits batch {batch_start}-{batch_start+BATCH_SIZE} attempt {attempt+1} failed: {e}")
                await asyncio.sleep(2 ** attempt)
        if not success:
            logger.error(f"Failed to import credits batch {batch_start}-{batch_start+BATCH_SIZE} after 5 attempts")
        else:
            logger.info(f"Credit users imported: {total}/{len(df)}")

    logger.info(f"Credits import done. Total users added: {total}")

# ================== 3. إنشاء طلبات قروض ==================
async def generate_loans(engine, count=LOAN_COUNT):
    logger.info(f"=== Generating {count} Loan Applications ===")
    async with engine.begin() as conn:
        users = await conn.execute(text("""
            SELECT id, monthly_income, credit_score FROM users
            WHERE role='CLIENT' AND monthly_income IS NOT NULL
            ORDER BY RANDOM() LIMIT :limit
        """), {"limit": count})
        users = users.fetchall()
        if not users:
            logger.warning("No credit users found.")
            return

        cars = await conn.execute(text("""
            SELECT id, price_consumer FROM cars
            WHERE is_available=true ORDER BY RANDOM() LIMIT :limit
        """), {"limit": count})
        cars = cars.fetchall()
        if not cars:
            logger.warning("No cars found.")
            return

        bank = await conn.execute(text("SELECT id FROM users WHERE role='BANK' LIMIT 1"))
        bank_id = bank.scalar()
        if not bank_id:
            bank_id = uuid.uuid4()
            await conn.execute(text("INSERT INTO users (id, email, hashed_password, full_name, role) VALUES (:id, 'bank@auto.com', 'x', 'Auto Bank', 'BANK')"), {"id": bank_id})
            logger.info("Created default bank.")

        total = 0
        for (user_id, income, score), (car_id, price) in zip(users, cars):
            income = income or 5000
            down_payment = round(price * random.uniform(0.1, 0.4), 2)
            tenure = random.choice([12, 24, 36, 48, 60])
            interest_rate = random.uniform(8, 15)
            loan_amount = price - down_payment
            monthly_installment = (loan_amount * interest_rate/100/12) / (1 - (1 + interest_rate/100/12)**(-tenure))
            status = random.choice(["PENDING", "APPROVED", "REJECTED"])
            await conn.execute(text("""
                INSERT INTO loan_applications (id, client_id, car_id, bank_id, loan_amount, down_payment, tenure_months, interest_rate, monthly_installment, status)
                VALUES (:id, :cid, :car, :bid, :amt, :dp, :ten, :ir, :mi, :st)
            """), {
                "id": uuid.uuid4(),
                "cid": user_id,
                "car": car_id,
                "bid": bank_id,
                "amt": loan_amount,
                "dp": down_payment,
                "ten": tenure,
                "ir": interest_rate,
                "mi": monthly_installment,
                "st": status
            })
            total += 1
        logger.info(f"Loan generation completed. Total: {total}")


# ... (باقي الكود كما هو) ...

async def main():
    # تقليل حجم تجمع الاتصالات لتجنب ثقل الخادم
    engine = create_async_engine(
        get_db_url(),
        echo=False,
        pool_size=2,         # كان 5 -> جعله أصغر
        max_overflow=2,      # كان 10 -> جعله أصغر
        connect_args={
            "timeout": 30,   # مهلة الاتصال بالثواني
            "command_timeout": 60  # مهلة الأوامر
        }
    )
    try:
        # يمكنك البدء ببيانات السيارات فقط كاختبار
        await import_cars(engine)
        await import_credits(engine)
        await generate_loans(engine)
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())