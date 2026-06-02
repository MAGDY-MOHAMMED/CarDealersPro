from os import path
import sys
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))
import logging
from http import HTTPStatus
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.database import Base
from app.main import app as original_app
from app.database import get_write_db, get_read_db
from app.models import User, UserRole, Car
from app.utils import get_password_hash
from app.core.security import Create_Access_Token
from app.routers import users, cars, auth, ratings, media, finance, ai
from app.core.exceptions import AppException
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exceptions import RequestValidationError

TEST_DATABASE_URL = "sqlite+aiosqlite:///file:memdb?mode=memory&cache=shared&uri=true"
EXCLUDE_TABLES = {"car_features"}


def pytest_configure(config):
    """
    Pytest hook that runs before session fixtures and event loop creation.
    Conditionally installs uvloop for non-Windows systems.
    """
    if sys.platform != "win32":
        try:
            import uvloop
            uvloop.install()
            print(" uvloop installed for test session")
        except ImportError:
            pass  # يشتغل بـ asyncio العادي
#fixture is for Context/Environment
# ========== تعطيل Logging لتسريع الاختبارات ==========
@pytest_asyncio.fixture(autouse=True)
# autouse=True means that this fixture will be automatically used for all tests
def disable_logging():
    logging.disable(logging.CRITICAL) # the highest level of logging is CRITICAL ,it describes numerically 50
    yield
    logging.disable(logging.NOTSET) # enable logging again , to prevent state pollution between tests

#why event_loop? because we want to use the same event loop for all tests and avoid creating a new event loop for each test ,
#  what event loop ? the asyncio event loop ,
#  why session ? because we want to use the same event loop for all tests in the same session
#
@pytest_asyncio.fixture(scope="session")
async def shared_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        tables = [t for name, t in Base.metadata.tables.items() if name not in EXCLUDE_TABLES]
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, tables=tables))
    yield engine
    await engine.dispose() # Close the engine after all tests are done

# we want to use the same engine for all tests and avoid creating a new engine for each test but many sessions in the same engine
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
            await session.flush() #why ? to generate the id for the objects before using them in other objects

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
        # commit automatically , to make sure all data is saved , it's automatically because of the async context manager ,which is defined in the db_session fixture
    return data
#why function scope? because we want to use the same session for all tests in the same function and avoid creating a new session for each test
# ========== Module-scoped Connection & Session ==========
@pytest_asyncio.fixture(scope="module")
async def module_connection(shared_engine):
    """اتصال واحد لكل ملف اختبار (Module)."""
    async with shared_engine.connect() as conn:
        await conn.begin()  # معاملة خارجية (لن تُحفَظ أبداً) , it's used to avoid committing the transaction , why ? because we don't want to commit the transaction , we want to rollback it after all tests are done
        yield conn # yield is used to return the connection to the test , pause here and break the execution of the function
        await conn.rollback() # rollback is used to undo any changes made to the database , after all tests are done

@pytest_asyncio.fixture(scope="module")
async def db_module_session(module_connection):
    """جلسة واحدة للموديول، كل الاختبارات تستخدمها مع Savepoints."""
    async_session = async_sessionmaker(bind=module_connection, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
# each test take a save point for isolation
# ========== Savepoint لكل اختبار (عزل تام) ==========
@pytest_asyncio.fixture(autouse=True)
async def test_savepoint(db_module_session):
    """يبدأ Savepoint قبل كل اختبار ويتراجع بعده."""
    await db_module_session.begin_nested() # Start a savepoint before each test ,begin_nested is used to start a nested transaction ,mechanism : it creates a savepoint in the transaction
    yield # pause here and break the execution of the function
    await db_module_session.rollback() # Rollback the savepoint after each test

# ========== تطبيق سريع للاختبارات ==========
@pytest_asyncio.fixture(scope="session")
async def test_app():
    app = FastAPI() # Create a new FastAPI app instance , without middleware

    # نسخ exception handlers (عشان نضمن نفس التنسيق)
    for exc_type, handler in original_app.exception_handlers.items(): # Copy exception handlers to ensure same formatting
        app.add_exception_handler(exc_type, handler) # Add exception handler to the new app instance

    app.include_router(users.router)
    app.include_router(cars.router)
    app.include_router(auth.router)
    app.include_router(ratings.router)
    app.include_router(media.router)
    app.include_router(finance.router)
    app.include_router(ai.router)

    return app

@pytest_asyncio.fixture
async def client(test_app, db_module_session):
    async def override_get_write_db(): # Override write database dependency , to use the same session for all tests
        yield db_module_session
    async def override_get_read_db(): # Override read database dependency , to use the same session for all tests
        yield db_module_session

    test_app.dependency_overrides[get_write_db] = override_get_write_db # Override write database dependency , to use the same session for all tests
    test_app.dependency_overrides[get_read_db] = override_get_read_db # Override read database dependency , to use the same session for all tests

    transport = ASGITransport(app=test_app) # Create ASGI transport for testing , ASGI is a Python standard for asynchronous web servers and applications
    async with AsyncClient(transport=transport, base_url="http://test") as ac: # Create async client for testing
        yield ac # Yield the async client for testing, pause here and break the execution of the function ,till the test is done

    test_app.dependency_overrides.clear()

# ========== Fixtures للكائنات ==========
@pytest_asyncio.fixture
async def dealer_user(db_module_session, base_data):
    return await db_module_session.get(User, base_data["dealer_id"])

@pytest_asyncio.fixture
async def client_user(db_module_session, base_data):
    return await db_module_session.get(User, base_data["client_id"])

@pytest_asyncio.fixture
async def admin_user(db_module_session, base_data):
    return await db_module_session.get(User, base_data["admin_id"])

@pytest_asyncio.fixture
async def bank_user(db_module_session, base_data):
    return await db_module_session.get(User, base_data["bank_id"])

@pytest_asyncio.fixture
async def car_id(base_data):
    return str(base_data["car_id"])
#why shared tokens ?, mechanism : create tokens once and reuse them across all tests
# ========== توكنات جاهزة ==========
@pytest_asyncio.fixture(scope="session")
async def shared_tokens(base_data):
    dealer_token = await Create_Access_Token(data={"sub": str(base_data["dealer_id"]), "role": "DEALER"})
    client_token = await Create_Access_Token(data={"sub": str(base_data["client_id"]), "role": "CLIENT"})
    admin_token = await Create_Access_Token(data={"sub": str(base_data["admin_id"]), "role": "ADMIN"})
    return {"dealer": dealer_token, "client": client_token, "admin": admin_token}
 #
@pytest_asyncio.fixture
async def dealer_headers(shared_tokens):
    return {"Authorization": f"Bearer {shared_tokens['dealer']}"}
#
@pytest_asyncio.fixture
async def client_headers(shared_tokens):
    return {"Authorization": f"Bearer {shared_tokens['client']}"}

@pytest_asyncio.fixture
async def admin_headers(shared_tokens):
    return {"Authorization": f"Bearer {shared_tokens['admin']}"}