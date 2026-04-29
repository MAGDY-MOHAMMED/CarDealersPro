# CarDealersPro

Car Dealers Platform - FastAPI + PostgreSQL + Alembic

## 📋 Prerequisites

- Python 3.10+
- PostgreSQL 15
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

### 6.1 Convert RSA Keys to Base64 (for Cloud Deployment)
```bash
# Convert private key to base64 (Linux/Mac)
base64 -w 0 private.pem

# Convert private key to base64 (Windows PowerShell)
[Convert]::ToBase64String([IO.File]::ReadAllBytes("private.pem"))

# Convert public key to base64 (Linux/Mac)
base64 -w 0 public.pem

# Convert public key to base64 (Windows PowerShell)
[Convert]::ToBase64String([IO.File]::ReadAllBytes("public.pem"))

# Add the base64 strings to your .env file:
# PRIVATE_KEY_BASE64=<base64_private_key>
# PUBLIC_KEY_BASE64=<base64_public_key>
```

**Note:** For local development, you can use the `.pem` files directly. For cloud deployment (Render, AWS, etc.), use the base64 environment variables.

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

## � Project Structure

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

## 🤖 Hugging Face Deployment

### Prerequisites
- Hugging Face account
- Hugging Face Space (Docker runtime)

### Step 1: Prepare Your Space

1. **Create a new Space**
   - Go to https://huggingface.co/spaces
   - Click "Create new Space"
   - Select "Docker" as runtime
   - Set visibility (Public/Private)

2. **Clone your Space**
   ```bash
   git clone https://huggingface.co/spaces/your-username/cardealerspro
   cd cardealerspro
   ```

### Step 2: Copy Project Files

1. **Copy all project files to the Space directory**
   ```bash
   # Copy from your local project
   cp -r /path/to/CarDealersPro/* .
   ```

2. **Ensure .gitignore excludes sensitive files**
   - `.env`
   - `*.pem`
   - `venv/`
   - `__pycache__/`

### Step 3: Set Environment Variables

1. **Go to your Space Settings → Variables**
2. **Add the following variables:**

   ```env
   DATABASE_URL=postgresql://username:password@hostname:5432/database_name
   ALGORITHM=RS256
   ACCESS_TOKEN_EXPIRE_MINUTES=60
   PRIVATE_KEY_BASE64=<your_base64_encoded_private_key>
   PUBLIC_KEY_BASE64=<your_base64_encoded_public_key>
   ```

3. **Or use an external database (recommended)**
   - Use Render, Supabase, or AWS RDS
   - Get the connection string
   - Set `DATABASE_URL` variable

### Step 4: Run Database Migrations

1. **Add a startup script** (optional but recommended)
   Create `start.sh`:
   ```bash
   #!/bin/bash
   python -m alembic upgrade head
   python app/main.py
   ```

2. **Update Dockerfile CMD**
   ```dockerfile
   CMD ["bash", "start.sh"]
   ```

### Step 5: Deploy

1. **Commit and push**
   ```bash
   git add .
   git commit -m "Deploy to Hugging Face"
   git push
   ```

2. **Wait for the build to complete**
   - Hugging Face will automatically build and deploy
   - Check the "Logs" tab for any errors

### Step 6: Test Your Application

1. **Access your Space**
   - URL: `https://huggingface.co/spaces/your-username/cardealerspro`

2. **Test health endpoint**
   ```bash
   curl https://huggingface.co/spaces/your-username/cardealerspro/health
   # Expected response: {"status": "ok"}
   ```

### Notes
- Hugging Face uses port 7860 by default
- The application automatically detects the PORT environment variable
- Free tier has limited resources (16GB RAM, 2 vCPU)
- Consider upgrading to Pro for production use

## ☁️ AWS Deployment

For comprehensive AWS deployment instructions, see [AWS_DEPLOYMENT.md](AWS_DEPLOYMENT.md).

### Quick Start with AWS Elastic Beanstalk

```bash
# Install AWS CLI and EB CLI
pip install awsebcli

# Initialize Elastic Beanstalk
eb init

# Create environment
eb create production

# Set environment variables
eb setenv DATABASE_URL="postgresql://..."
eb setenv ALGORITHM="RS256"
eb setenv PRIVATE_KEY_BASE64="..."
eb setenv PUBLIC_KEY_BASE64="..."

# Deploy
eb deploy
```

### AWS Services Used

- **Elastic Beanstalk** - Application deployment
- **RDS PostgreSQL** - Managed database
- **CloudWatch** - Monitoring and logging
- **Secrets Manager** - Secure credential storage

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

### Cloud Deployment Issues
- Check environment variables are set correctly
- Verify database connection string format
- Check logs in the cloud platform dashboard
- Ensure RSA keys are base64 encoded