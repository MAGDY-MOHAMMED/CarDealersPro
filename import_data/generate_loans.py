# generate_loans.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import asyncio, os, sys, logging, random, uuid
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("LoanGenerator")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# نفس دالة get_db_url...

async def generate_loan_applications(count=500):
    engine = create_async_engine(get_db_url(), echo=False)
    async with engine.begin() as conn:
        # جلب مستخدمين عشوائيين (غير بنوك)
        users = await conn.execute(text("SELECT id, monthly_income, credit_score FROM users WHERE role='CLIENT' ORDER BY RANDOM() LIMIT :count"), {"count": count})
        users = users.fetchall()
        # جلب سيارات متاحة
        cars = await conn.execute(text("SELECT id, price_consumer FROM cars WHERE is_available=true ORDER BY RANDOM() LIMIT :count"), {"count": count})
        cars = cars.fetchall()
        # جلب بنك واحد على الأقل
        bank = await conn.execute(text("SELECT id FROM users WHERE role='BANK' LIMIT 1"))
        bank_id = bank.scalar()
        if not bank_id:
            # إنشاء بنك افتراضي
            bank_id = uuid.uuid4()
            await conn.execute(text("INSERT INTO users (id, email, hashed_password, full_name, role) VALUES (:id, 'bank@auto.com', 'x', 'Auto Bank', 'BANK')"), {"id": bank_id})

        for (user_id, income, score), (car_id, price) in zip(users, cars):
            if income is None or income <= 0:
                income = 5000
            down_payment = round(price * random.uniform(0.1, 0.4), 2)
            tenure = random.choice([12, 24, 36, 48, 60])
            interest_rate = random.uniform(8, 15)
            status = random.choice(['PENDING', 'APPROVED', 'REJECTED'])
            app_id = uuid.uuid4()
            await conn.execute(text("""
                INSERT INTO loan_applications (id, client_id, car_id, bank_id, loan_amount, down_payment, tenure_months, interest_rate, monthly_installment, status)
                VALUES (:id, :cid, :car, :bid, :amt, :dp, :ten, :ir, :mi, :st)
            """), {
                "id": app_id, "cid": user_id, "car": car_id, "bid": bank_id,
                "amt": price - down_payment, "dp": down_payment, "ten": tenure,
                "ir": interest_rate, "mi": (price - down_payment) * (interest_rate/100/12) / (1 - (1 + interest_rate/100/12)**-tenure),
                "st": status
            })
    await engine.dispose()
    logger.info(f"Generated {count} loan applications.")

if __name__ == "__main__":
    asyncio.run(generate_loan_applications(500))