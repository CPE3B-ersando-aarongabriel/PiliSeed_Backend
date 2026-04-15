import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _parse_cors_origins(raw_origins: str | None) -> list[str]:
    if not raw_origins:
        return ["*"]

    origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
    return origins or ["*"]


@dataclass(slots=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "PiliSeed Backend")
    app_version: str = os.getenv("APP_VERSION", "1.0.0")
    environment: str = os.getenv("ENVIRONMENT", "development")

    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    openai_timeout_seconds: float = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "45"))

    mongodb_url: str = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    database_name: str = os.getenv("DATABASE_NAME", "piliseed")

    trefle_api_key: str = os.getenv("TREFLE_API_KEY", "")
    trefle_timeout_seconds: float = float(os.getenv("TREFLE_TIMEOUT_SECONDS", "6"))

    cors_origins: list[str] = field(
        default_factory=lambda: _parse_cors_origins(os.getenv("CORS_ORIGINS"))
    )


settings = Settings()
