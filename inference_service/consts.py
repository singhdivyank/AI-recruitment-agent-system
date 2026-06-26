"""
Core application configuration using Pydantic Settings.
All values are loaded from environment variables / .env file.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"          # 384-dim, fast
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    cache_dir: str = "models"


@lru_cache
def get_settings() -> Settings:
    return Settings()
