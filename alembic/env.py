from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool, create_engine
from alembic import context
import os
from dotenv import load_dotenv

# 1. استيراد الـ Base والموديلات (تأكد من استيراد الكل عشان الـ Constraints تظهر)
from app.database import Base 
from app.models import User, Car, CarRating, UserRating

# 2. تحميل ملف الـ .env
load_dotenv()

# 3. Try to get DATABASE_URL from environment (Render provides this)
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # Use Render's DATABASE_URL (already in postgresql:// format)
    database_url = DATABASE_URL
else:
    # 4. جلب البيانات من الـ .env اللي إنت بعته
    DB_USER = os.getenv("DATABASE_USERNAME")
    DB_PASS = os.getenv("DATABASE_PASSWORD")
    DB_HOST = os.getenv("DATABASE_HOSTNAME")
    DB_PORT = os.getenv("DATABASE_PORT")
    DB_NAME = os.getenv("DATABASE_NAME")

    # 5. بناء الـ URL
    database_url = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

config = context.config #

# 5. ربط الـ URL بـ Alembic ديناميكياً
config.set_main_option("sqlalchemy.url", database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    # استخدام create_engine مباشرة بالـ URL اللي بنيناه
    connectable = create_engine(database_url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()