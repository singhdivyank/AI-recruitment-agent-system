CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS profile_embeddings_vector_idx
ON profile_embeddings
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 50)
"""

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS profile_embeddings (
    id               SERIAL PRIMARY KEY,
    candidate_id     TEXT NOT NULL UNIQUE,
    name             TEXT,
    email            TEXT,
    location         TEXT,
    experience_years FLOAT DEFAULT 0,
    skills           TEXT[],
    sources          TEXT[],
    profile_text     TEXT,
    embedding        vector({dimensions}),
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
)
"""

EMBEDDING_INGESTION = """
INSERT INTO profile_embeddings
    (candidate_id, name, email, location, experience_years,
        skills, sources, profile_text, embedding)
VALUES
    (:cid, :name, :email, :location, :exp,
        :skills, :sources, :profile_text, :embedding::vector)
ON CONFLICT (candidate_id) DO UPDATE SET
    name             = EXCLUDED.name,
    location         = EXCLUDED.location,
    experience_years = EXCLUDED.experience_years,
    skills           = EXCLUDED.skills,
    sources          = EXCLUDED.sources,
    profile_text     = EXCLUDED.profile_text,
    embedding        = EXCLUDED.embedding,
    updated_at       = NOW()
"""

EMBEDDING_INGESTION_BATCHES = """
INSERT INTO profile_embeddings
    (candidate_id, name, email, location, experience_years,
        skills, sources, profile_text, embedding)
VALUES
    (:cid, :name, :email, :location, :exp,
        :skills, :sources, :profile_text, :embedding::vector)
ON CONFLICT (candidate_id) DO UPDATE SET
    name             = EXCLUDED.name,
    location         = EXCLUDED.location,
    experience_years = EXCLUDED.experience_years,
    skills           = EXCLUDED.skills,
    sources          = EXCLUDED.sources,
    profile_text     = EXCLUDED.profile_text,
    embedding        = EXCLUDED.embedding,
    updated_at       = NOW()
"""

RETRIEVAL = """
SELECT
    candidate_id,
    name,
    location,
    experience_years,
    skills,
    sources,
    profile_text,
    embedding <=> :query_vector::vector AS distance
    1 - (embedding <=> :query_vector::vector) AS similarity_score
FROM profile_embeddings
{where_clause}
ORDER BY distance ASC
LIMIT {top_k}
"""