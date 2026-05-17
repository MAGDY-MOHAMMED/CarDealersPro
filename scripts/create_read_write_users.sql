-- SQL Script to Create 3-Tier Database Users in PostgreSQL
-- This script creates three database users:
-- 1. cardealers_primary_user: Has full access (general operations)
-- 2. cardealers_write_user: Has full access (API POST, PUT, DELETE)
-- 3. cardealers_read_user: Has read-only access (GET and reports)

-- Connect to the database as postgres superuser
-- psql -U postgres -d CarDealersPro -f create_read_write_users.sql

-- Create primary user (for general operations)
CREATE USER IF NOT EXISTS cardealers_primary_user WITH PASSWORD 'your_secure_primary_password_here';

-- Grant all privileges on all tables in the public schema to primary user
GRANT CONNECT ON DATABASE CarDealersPro TO cardealers_primary_user;
GRANT USAGE ON SCHEMA public TO cardealers_primary_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO cardealers_primary_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO cardealers_primary_user;

-- Grant usage on sequences to primary user (needed for auto-increment IDs)
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO cardealers_primary_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO cardealers_primary_user;

-- Create write user (for API POST, PUT, DELETE operations)
CREATE USER IF NOT EXISTS cardealers_write_user WITH PASSWORD 'your_secure_write_password_here';

-- Grant all privileges on all tables in the public schema to write user
GRANT CONNECT ON DATABASE CarDealersPro TO cardealers_write_user;
GRANT USAGE ON SCHEMA public TO cardealers_write_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO cardealers_write_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO cardealers_write_user;

-- Grant usage on sequences to write user (needed for auto-increment IDs)
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO cardealers_write_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO cardealers_write_user;

-- Create read user (for GET operations and reports)
CREATE USER IF NOT EXISTS cardealers_read_user WITH PASSWORD 'your_secure_read_password_here';

-- Grant read-only access to read user
GRANT CONNECT ON DATABASE CarDealersPro TO cardealers_read_user;
GRANT USAGE ON SCHEMA public TO cardealers_read_user;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO cardealers_read_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO cardealers_read_user;

-- Grant usage on sequences to read user (needed for reading auto-increment IDs)
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO cardealers_read_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO cardealers_read_user;

-- Revoke write privileges from read user (ensure read-only)
REVOKE INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public FROM cardealers_read_user;

-- Verify permissions
\du cardealers_primary_user
\du cardealers_write_user
\du cardealers_read_user

-- Display privileges on tables
\dp public.*

-- Instructions:
-- 1. Replace 'your_secure_primary_password_here', 'your_secure_write_password_here', and 'your_secure_read_password_here' with strong passwords
-- 2. Run this script as postgres superuser:
--    psql -U postgres -d CarDealersPro -f create_read_write_users.sql
-- 3. Update your .env file with the new credentials:
--    DATABASE_PRIMARY_USER=cardealers_primary_user
--    DATABASE_PRIMARY_PASSWORD=your_secure_primary_password_here
--    DATABASE_WRITE_USER=cardealers_write_user
--    DATABASE_WRITE_PASSWORD=your_secure_write_password_here
--    DATABASE_READ_USER=cardealers_read_user
--    DATABASE_READ_PASSWORD=your_secure_read_password_here
