import json
from typing import Annotated, List

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


DEFAULT_CORS_ORIGINS: List[str] = []
LOCAL_DEVELOPMENT_CORS_REGEX = r"^https?://(?:localhost|127\.0\.0\.1)(?::[0-9]{1,5})?$"


class Settings(BaseSettings):
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"
    DB_HOST: str = "localhost"
    DB_PORT: str = "5432"
    DB_NAME: str = "postulaciones_db"

    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/postulaciones_db"
    SECRET_KEY: str = "change-me-in-local-env"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    HOST: str = "0.0.0.0"
    PORT: int = 8000
    CORS_ORIGINS: Annotated[List[str], NoDecode] = DEFAULT_CORS_ORIGINS.copy()

    ENVIRONMENT: str = "development"
    ENABLE_SWAGGER: bool = False
    EXPOSE_RESET_CODE: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            try:
                value = json.loads(raw)
            except json.JSONDecodeError:
                value = [origin.strip() for origin in raw.split(",")]

        if not isinstance(value, (list, tuple, set)):
            raise ValueError(
                "CORS_ORIGINS debe ser una lista o texto separado por comas"
            )

        origins = []
        for origin in value:
            normalized = str(origin).strip().rstrip("/")
            if normalized and normalized not in origins:
                origins.append(normalized)
        return origins

    @field_validator("ALGORITHM")
    @classmethod
    def validate_algorithm(cls, value: str) -> str:
        algorithm = value.strip().upper()
        if algorithm not in {"HS256", "HS384", "HS512"}:
            raise ValueError("ALGORITHM debe ser HS256, HS384 o HS512")
        return algorithm

    @field_validator("ENVIRONMENT")
    @classmethod
    def normalize_environment(cls, value: str) -> str:
        return value.strip().lower()

    @model_validator(mode="after")
    def validate_production_settings(self):
        if self.ENVIRONMENT in {"production", "prod"}:
            if self.SECRET_KEY == "change-me-in-local-env" or len(self.SECRET_KEY) < 32:
                raise ValueError(
                    "SECRET_KEY debe tener al menos 32 caracteres en produccion"
                )
            if "*" in self.CORS_ORIGINS:
                raise ValueError("CORS_ORIGINS no puede contener '*' en produccion")
        return self

    @property
    def DEBUG(self) -> bool:
        return self.ENVIRONMENT == "development"

    @property
    def CORS_ORIGIN_REGEX(self) -> str | None:
        """Permite frontends locales en cualquier puerto solo durante desarrollo."""
        if self.DEBUG:
            return LOCAL_DEVELOPMENT_CORS_REGEX
        return None


settings = Settings()
