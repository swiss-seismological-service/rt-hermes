-- Initialize Prefect PostgreSQL database extensions
-- This script is executed automatically on database initialization
-- by the PostgreSQL Docker container

-- Create pg_trgm extension for trigram-based text search
-- Required by Prefect v3 for efficient text search operations
CREATE EXTENSION IF NOT EXISTS pg_trgm;
