import json
import os
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "postgres")
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: str = os.getenv("DB_PORT", "5432")
    DB_NAME: str = os.getenv("DB_NAME", "postulaciones_db")

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/postulaciones_db"
    )
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-local-env")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    CORS_ORIGINS: List[str] = json.loads(os.getenv("CORS_ORIGINS", '["*"]'))
    
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = ENVIRONMENT == "development" or os.getenv("ENABLE_SWAGGER", "false").lower() == "true"
    SWAGGER_ALWAYS_ON: bool = os.getenv("ENABLE_SWAGGER", "false").lower() == "true"

    @field_validator("DEBUG", "SWAGGER_ALWAYS_ON", mode="before")
    @classmethod
    def parse_bool_flags(cls, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes", "y", "on", "debug", "development"}:
                return True
            if normalized in {"false", "0", "no", "n", "off", "release", "prod", "production"}:
                return False
        return value

    class Config:
        env_file = ".env"
        case_sensitive = True



settings = Settings()
