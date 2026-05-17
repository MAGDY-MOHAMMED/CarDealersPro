import asyncio
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import get_write_db, get_read_db, Base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
#this file for setting up the test environment



TEST_DATABASE_URL= "sqlite+aiosqlite:///./test.db"
#
@pytest_asyncio.fixture(scope="session") #scope="session" means this fixture will be created once for all tests in the session
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False) #echo=False means no sql queries will be printed to console
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    #drop all tables after all tests are done
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
 
 #create a database session for each test
@pytest_asyncio.fixture
async def db_session(test_engine):
    async_session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    async with async_session_factory() as session:
        yield session

# create an api client for each test
@pytest_asyncio.fixture
async def client(test_engine, db_session): #test_engine is the database engine, db_session is the database session
    async def override_get_write_db():#override the get_write_db dependency
        yield db_session
    
    async def override_get_read_db():#override the get_read_db dependency why ? to allow read operations on the database
        yield db_session
    
    app.dependency_overrides[get_write_db] = override_get_write_db #override the get_write_db dependency why ? to allow write operations on the database
    app.dependency_overrides[get_read_db] = override_get_read_db #override the get_read_db dependency why ? to allow read operations on the database
    #create an async transport for the client
    transport = ASGITransport(app=app) #create an async transport
    async with AsyncClient(transport=transport, base_url="http://test") as ac: #create an async client
        yield ac

    app.dependency_overrides.clear()

@pytest_asyncio.fixture
async def dealer_token(client, test_engine):
    # create user, set role to DEALER via raw SQL
    
    return token


@pytest_asyncio.fixture
async def client_token(client, test_engine):
    # create user, set role to CLIENT via raw SQL
    
    return token

@pytest_asyncio.fixture
async def bank_id(client, test_engine):
    # create bank user, set role to BANK via raw SQL
    
    return bank_id


@pytest_asyncio.fixture
async def car_id(client, dealer_token):


@pytest.mark.asyncio
async def test_full_flow(client, dealer_token, client_token, bank_id, car_id):
    #apply loan
    loan_data= {
        "client_id": extract_id_from_token(client_token),
        "car_id": car_id,
        "bank_id": bank_id,
        "down_payment": 200000,
        "tenure_months": 36
    }
    response = await client.post("/finance/applications", json=loan_data, headers=client_token_headers)
    assert response.status_code == 200
    app_id = response.json()["id"]
    # Approve loan (admin or bank role needed; we'll use dealer as admin for test)
    # Actually we need an admin or bank role. We'll create an admin fixture.


@pytest_asyncio.fixture
async def dealer_headers(dealer_token):
    return {"Authorization": f"Bearer {dealer_token}"}

@pytest_asyncio.fixture
async def client_headers(client_token):
    return {"Authorization": f"Bearer {client_token}"}

@pytest_asyncio.fixture
async def dealer_id(dealer_user):
    return str(dealer_user.id)

@pytest_asyncio.fixture
async def client_id(client_user):
    return str(client_user.id)


@pytest_asyncio.fixture
async def admin_user(db_session):
    user = User(
        email="admin@test.com",
        hashed_password=get_password_hash("admin123"),
        full_name="Admin",
        role=UserRole.ADMIN,
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

@pytest_asyncio.fixture
async def admin_token(client, admin_user):
    res = await client.post("/auth/login", json={
        "email": admin_user.email,
        "password": "admin123"
    })
    return res.json()["access_token"]

@pytest_asyncio.fixture
async def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}
