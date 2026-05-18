-- Initialize ev_battery database on server2
-- Run as postgres superuser

CREATE USER ev_battery_user WITH PASSWORD 'ev_battery_pass';
CREATE DATABASE ev_battery OWNER ev_battery_user;
GRANT ALL PRIVILEGES ON DATABASE ev_battery TO ev_battery_user;

\c ev_battery

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Grant schema permissions
GRANT ALL ON SCHEMA public TO ev_battery_user;

-- Create hatchet tables if using Hatchet's built-in db
-- (Hatchet manages its own tables separately)

\echo 'Database ev_battery created successfully'
\echo 'Run: alembic upgrade head'
