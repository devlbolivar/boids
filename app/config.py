from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    SECRET_KEY: str = "supersecretkeychangeinprod"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # PostgreSQL Database URL
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/boids_db"

    # Redis Client URL
    REDIS_URL: str = "redis://localhost:6379/0"

    # Encryption key for sensitive data (Apollo keys, email accounts)
    # Must be 32-byte URL-safe base64-encoded key
    MASTER_ENCRYPTION_KEY: str = "3k4b5d6e7f8g9h0i1j2k3l4m5n6o7p8q9r0s1t2u3v4="

    # Apollo.io API key (global, shared plan). Tenants can override via api_keys_enc.
    APOLLO_API_KEY: str = ""

    # OpenAI API key for embeddings
    OPENAI_API_KEY: str = ""

    # Qdrant vector database URL
    QDRANT_URL: str = "http://localhost:6333"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
