-- init_db.sql
-- Runs once on first postgres container boot (only when data volume is empty).
-- The database named by POSTGRES_DB is already created by the entrypoint before
-- this script runs, so we just need to set up extensions and schemas.

\connect recruitment

-- pgvector extension (required for RAG pipeline)
CREATE EXTENSION IF NOT EXISTS vector;

-- Confirm setup
SELECT 'Database initialized: ' || current_database() AS status;
SELECT 'pgvector version: ' || extversion AS vector_status
FROM pg_extension WHERE extname = 'vector';