import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool

from app.config import settings


def _crear_engine():
    url = settings.DATABASE_URL.strip()
    opciones = {
        "echo": settings.DEBUG,
        "pool_pre_ping": True,
    }

    if url.startswith("sqlite"):
        opciones["connect_args"] = {"check_same_thread": False}
    else:
        opciones["connect_args"] = {
            "connect_timeout": 10,
            "keepalives": 1,
            "keepalives_idle": 30,
            "client_encoding": "utf8",
        }
        opciones["pool_recycle"] = 3600

    if os.getenv("VERCEL") == "1":
        opciones["poolclass"] = NullPool
        opciones.pop("pool_recycle", None)

    return create_engine(url, **opciones)


engine = _crear_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
