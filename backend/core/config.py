"""
Core application configuration using Pydantic Settings.
All values are loaded from environment variables / .env file.

GitHub-safe: every field has a default so the app starts without a .env file.
Real secrets (API keys) default to "" and are validated at runtime when first used.
"""
from functools import lru_cache
from typing import List
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    cors_origins: str = "http://localhost:3000"
    google_api_key: str = ""
    gemini_model: str = "gemini-2.5-pro-preview-05-06"
    gemini_flash_model: str = "gemini-2.0-flash"
    pinecone_api_key: str = ""
    pinecone_index_name: str = "recruitment-profiles"
    pinecone_environment: str = "us-east-1"
    langchain_api_key: str = ""
    langchain_tracing_v2: str = "true"
    langchain_project: str = "recruitment-agent"
    langchain_endpoint: str = "https://api.smith.langchain.com"
    postgres_user: str = ""
    postgres_password: str = ""
    database_url: str = ""          # assembled post-init
    redis_password: str = ""
    redis_url: str = ""             # assembled post-init
    elasticsearch_url: str = "http://elasticsearch:9200"
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    hf_dataset: str = "json_resume_dataset"
    hf_token: str = ""
    max_tokens_per_jd: int = 500_000
    max_cost_per_jd_usd: float = 5.00
    max_llm_retries: int = 3
    daily_budget_usd: float = 100.00
    otel_exporter_otlp_endpoint: str = "http://otel-collector:4317"
    otel_service_name: str = ""
    grafana_password: str = ""
    embedding_model = "all-MiniLM-L6-v2"          # 384-dim, fast
    reranker_model = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    @model_validator(mode="after")
    def assemble_urls(self) -> "Settings":
        # Only build if not explicitly provided in env
        if not self.database_url:
            self.database_url = (
                f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
                f"@postgres:5432/{self.postgres_user}"
            )
        if not self.redis_url:
            self.redis_url = f"redis://:{self.redis_password}@redis:6379/0"
        return self

    # ─── Derived helpers ──────────────────────────────────────

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def gemini_pro_input_cost_per_token(self) -> float:
        return 3.50 / 1_000_000

    @property
    def gemini_pro_output_cost_per_token(self) -> float:
        return 10.50 / 1_000_000

    @property
    def gemini_flash_input_cost_per_token(self) -> float:
        return 0.10 / 1_000_000

    @property
    def gemini_flash_output_cost_per_token(self) -> float:
        return 0.40 / 1_000_000


@lru_cache
def get_settings() -> Settings:
    return Settings()