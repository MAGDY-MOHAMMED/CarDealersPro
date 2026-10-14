import sys
import os
os.environ.setdefault("MIN_DISK_SPACE_MB", "0")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")
import sys
import base64
import asyncio
import logging
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy import text
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from app.database import Base
from app.main import app as original_app
from app.database import get_write_db, get_read_db
from app.models import User, UserRole, Car
from app.utils import get_password_hash
from app.core.security import Create_Access_Token
from app.routers import users, cars, auth, ratings, media, finance, ai
from dotenv import load_dotenv
load_dotenv()
# إعدادات PostgreSQL
DB_USER = os.getenv("TEST_DATABASE_USERNAME", "postgres")
DB_PASS = os.getenv("TEST_DATABASE_PASSWORD", "postgres")
DB_HOST = os.getenv("TEST_DATABASE_HOSTNAME", "localhost")
DB_PORT = os.getenv("TEST_DATABASE_PORT", "5433")    # 5433 محلياً، وفي CI سنمرر 5432
DB_NAME = os.getenv("TEST_DATABASE_NAME", "cardealerspro_test")

ADMIN_DB_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/postgres"
TEST_DB_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# ========== uvloop ==========
def pytest_configure(config):
    # uvloop.install() is deprecated on Python 3.12+. Tests don't need the
    # extra throughput — the default asyncio loop is fine and avoids warnings.
    pass

@pytest_asyncio.fixture(autouse=True)
def disable_logging():
    logging.disable(logging.CRITICAL)
    yield
    logging.disable(logging.NOTSET)

# ========== مفاتيح JWT وهمية ==========
#the mechanism ,
@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_keys():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048) 
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    import app.core.config as config_module
    config_module.settings.PRIVATE_KEY_BASE64 = base64.b64encode(private_pem).decode()
    config_module.settings.PUBLIC_KEY_BASE64 = base64.b64encode(public_pem).decode()

    for attr in ('private_key', 'public_key'):
        if hasattr(config_module.settings, attr):
            delattr(config_module.settings, attr)
    yield

# ========== محرك الاختبار (NullPool) ==========
@pytest_asyncio.fixture(scope="session")
async def shared_engine():
    # إنشاء قاعدة الاختبار
    engine = create_async_engine(ADMIN_DB_URL, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        await conn.execute(text(f"DROP DATABASE IF EXISTS {DB_NAME} WITH (FORCE)"))
        await conn.execute(text(f"CREATE DATABASE {DB_NAME}"))
    await engine.dispose()

    # المحرك الرئيسي مع NullPool (يمنع مهام asyncpg الخلفية)
    engine = create_async_engine(
        TEST_DB_URL, echo=False, poolclass=NullPool
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()

    # تنظيف
    engine = create_async_engine(ADMIN_DB_URL, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        await conn.execute(text(f"DROP DATABASE IF EXISTS {DB_NAME} WITH (FORCE)"))
    await engine.dispose()

# ========== بيانات أساسية ==========
@pytest_asyncio.fixture(scope="session")
async def base_data(shared_engine):
    async_session = async_sessionmaker(shared_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        async with session.begin():
            dealer = User(
                email="dealer@test.com", hashed_password=get_password_hash("dealer123"),
                full_name="Test Dealer", role=UserRole.DEALER, subscription_plan="FREE",
                inventory_count=0, is_active=True
            )
            session.add(dealer)
            client = User(
                email="client@test.com", hashed_password=get_password_hash("client123"),
                full_name="Test Client", role=UserRole.CLIENT, monthly_income=50000.0,
                credit_score=700, is_active=True
            )
            session.add(client)
            admin = User(
                email="admin@test.com", hashed_password=get_password_hash("admin123"),
                full_name="Admin", role=UserRole.ADMIN, is_active=True
            )
            session.add(admin)
            bank = User(
                email="bank@test.com", hashed_password=get_password_hash("bank123"),
                full_name="Test Bank", role=UserRole.BANK,
                bank_min_dp_new=15.0, bank_min_dp_used=20.0,
                bank_max_months_new=60, bank_max_months_used=48,
                bank_rate_new=12.0, bank_rate_used=14.0, is_active=True
            )
            session.add(bank)
            await session.flush()

            car = Car(
                brand="Toyota", model="Corolla", year=2022, price_consumer=500000.0,
                price_dealer=480000.0, condition="used", owner_id=dealer.id,
                is_available=True, is_deleted=False, published=True
            )
            session.add(car)
            await session.flush()

            data = {
                "dealer_id": dealer.id, "client_id": client.id,
                "admin_id": admin.id, "bank_id": bank.id, "car_id": car.id,
            }
    return data

# ========== جلسة قاعدة بيانات لكل اختبار ==========
@pytest_asyncio.fixture
async def db_session(shared_engine):
    async with shared_engine.connect() as conn:
        await conn.begin()
        async_session = async_sessionmaker(bind=conn, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            await session.begin_nested()
            yield session
            await session.rollback()
        await conn.rollback()

# ========== تطبيق FastAPI ==========
@pytest_asyncio.fixture(scope="session")
async def test_app():
    app = FastAPI()
    for exc_type, handler in original_app.exception_handlers.items():
        app.add_exception_handler(exc_type, handler)
    app.include_router(users.router)
    app.include_router(cars.router)
    app.include_router(auth.router)
    app.include_router(ratings.router)
    app.include_router(media.router)
    app.include_router(finance.router)
    app.include_router(ai.router)
    return app

@pytest_asyncio.fixture
async def client(test_app, db_session):
    async def override_get_write_db():
        yield db_session
    async def override_get_read_db():
        yield db_session

    test_app.dependency_overrides[get_write_db] = override_get_write_db
    test_app.dependency_overrides[get_read_db] = override_get_read_db

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    test_app.dependency_overrides.clear()

# ========== كائنات المستخدمين ==========
@pytest_asyncio.fixture
async def dealer_user(db_session, base_data):
    return await db_session.get(User, base_data["dealer_id"]) 

@pytest_asyncio.fixture
async def client_user(db_session, base_data):
    return await db_session.get(User, base_data["client_id"]) 

@pytest_asyncio.fixture
async def admin_user(db_session, base_data):
    return await db_session.get(User, base_data["admin_id"]) 

@pytest_asyncio.fixture
async def bank_user(db_session, base_data):
    return await db_session.get(User, base_data["bank_id"]) 

@pytest_asyncio.fixture
async def car_id(base_data):
    return str(base_data["car_id"])

# ========== توكنات ==========
@pytest_asyncio.fixture(scope="session")
async def shared_tokens(base_data):
    dealer_token = await Create_Access_Token(data={"sub": str(base_data["dealer_id"]), "role": "DEALER"})
    client_token = await Create_Access_Token(data={"sub": str(base_data["client_id"]), "role": "CLIENT"})
    admin_token = await Create_Access_Token(data={"sub": str(base_data["admin_id"]), "role": "ADMIN"})
    return {"dealer": dealer_token, "client": client_token, "admin": admin_token}

@pytest_asyncio.fixture
async def dealer_headers(shared_tokens):
    return {"Authorization": f"Bearer {shared_tokens['dealer']}"}

@pytest_asyncio.fixture
async def client_headers(shared_tokens):
    return {"Authorization": f"Bearer {shared_tokens['client']}"}

@pytest_asyncio.fixture
async def admin_headers(shared_tokens):
    return {"Authorization": f"Bearer {shared_tokens['admin']}"}