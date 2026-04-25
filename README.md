# CarDealersPro

Car Dealers Platform - FastAPI + PostgreSQL + Alembic

## 📋 Prerequisites

- Python 3.10+
- PostgreSQL 14+
- Windows (with Windsurf IDE)

## 🚀 Quick Setup (New Computer)

### 1. Copy the Project
```bash
# Copy the entire project folder to the new computer
# Exclude: venv/, .env, *.pem files
```

### 2. Create Virtual Environment
```bash
cd CarDealersPro
python -m venv venv
```

### 3. Activate Virtual Environment
```bash
# Windows
venv\Scripts\activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Setup Environment Variables
```bash
# Copy .env.example to .env
copy .env.example .env

# Edit .env with your database credentials
```

### 6. Generate RSA Keys for JWT
```bash
# Generate private key
openssl genrsa -out private.pem 2048

# Generate public key
openssl rsa -in private.pem -pubout -out public.pem
```

### 7. Setup Database
```bash
# Create PostgreSQL database named "CarDealersPro"
# Update DATABASE_* settings in .env
```

### 8. Run Migrations
```bash
# Using the migrate script (recommended)
venv\Scripts\python migrate.py --no-generate

# Or using Alembic directly
.\venv\Scripts\alembic upgrade head
```

### 9. Run the Application
```bash
# Using uvicorn
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 📁 Project Structure

```
CarDealersPro/
├── app/
│   ├── core/          # Core logic (auth, config, logging)
│   ├── models.py      # SQLAlchemy models
│   ├── schemas.py     # Pydantic schemas
│   ├── routers/       # FastAPI routers (users, cars, auth, ratings)
│   ├── database.py    # Database connection
│   └── utils/         # Utility functions
├── alembic/           # Database migrations
├── core/              # Domain logic (auth, base, validator)
├── .env.example       # Environment variables template
├── requirements.txt   # Python dependencies
└── migrate.py         # Migration automation script
```

## 🔐 Environment Variables

```env
DATABASE_HOSTNAME=localhost
DATABASE_PORT=5432
DATABASE_NAME=CarDealersPro
DATABASE_USERNAME=postgres
DATABASE_PASSWORD=your_password
ALGORITHM=RS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

## 📝 Migration Commands

### Using migrate.py (Recommended)
```bash
# Check migration status
venv\Scripts\python migrate.py --status-only

# Generate new migration
venv\Scripts\python migrate.py "add new column"

# Apply pending migrations
venv\Scripts\python migrate.py --no-generate

# View migration history
venv\Scripts\python migrate.py --history
```

### Using Alembic Directly
```bash
# Check current revision
.\venv\Scripts\alembic current

# Check migration history
.\venv\Scripts\alembic history

# Generate new migration
.\venv\Scripts\alembic revision --autogenerate -m "add new column"

# Apply migrations
.\venv\Scripts\alembic upgrade head

# Downgrade to previous version
.\venv\Scripts\alembic downgrade -1
```

## 🔑 User Roles

- **CLIENT** - Default user role
- **DEALER** - Can list cars
- **BANK** - Can view car listings
- **INSPECTOR** - Can rate cars
- **ADMIN** - Administrative access

## 🛡️ Security Notes

- **Never commit** `.env`, `*.pem`, or `venv/` to version control
- RSA keys are used for JWT signing (RS256 algorithm)
- Passwords are hashed using bcrypt
- Request ID injection for debugging and tracing

## 🐛 Troubleshooting

### Migration Errors
```bash
# Check if database is up to date
venv\Scripts\alembic current

# Check migration history
venv\Scripts\alembic history
```

### Database Connection Errors
- Verify PostgreSQL is running
- Check `.env` database credentials
- Ensure database "CarDealersPro" exists

### Import Errors
- Ensure virtual environment is activated
- Run `pip install -r requirements.txt`

## 🐳 Docker Setup

### Prerequisites
- Docker Desktop installed and running
- Docker Compose
- `.env` file with environment variables

### Quick Start with Docker

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop all services
docker-compose down

# Rebuild after code changes
docker-compose up -d --build api
```

### Services
- **API** - FastAPI application (port 8000)
- **PostgreSQL** - Database (port 5432)

### Health Check
```bash
# Check if API is running
curl http://localhost:8000/health
# Response: {"status": "ok"}
```

### Docker Commands

```bash
# Build only the API image
docker build -t cardealers-api .

# Run API container
docker run -p 8000:8000 cardealers-api

# Execute commands in container
docker-compose exec api bash

# View container logs
docker-compose logs api

# Stop specific service
docker-compose stop api
```

### Docker Compose Configuration

- Database name: `CarDealersPro`
- Database user: `postgres`
- Database password: Set in `.env` file
- Network: `main-net`
- Volume: `postgres-data` (auto-created by Docker Compose)

### Notes
- RSA keys (`*.pem`) must be generated before running in Docker
- Environment variables are loaded from `.env` file
- Logs are printed to console (Docker/AWS compatible)
- No file logging - logs are captured by Docker/AWS logging systems
