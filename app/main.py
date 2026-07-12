import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text

from app.config import settings
from app.infrastructure.database.connection import Base, engine
from app.interface.api.contacto.router import router as contacto_router
from app.interface.api.iam.router import router as iam_router
from app.interface.api.metrica.router import router as metrica_router
from app.interface.api.postulacion.router import router as postulacion_router
from app.interface.api.puesto.router import router as puesto_router


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
UPLOADS_DIR = PROJECT_ROOT / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def _ensure_column(table_name: str, column_name: str, ddl: str) -> None:
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns(table_name)}
    if column_name in columns:
        return

    with engine.begin() as connection:
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {ddl}"))
    logger.info("Columna %s.%s creada para compatibilidad.", table_name, column_name)


def _ensure_runtime_schema() -> None:
    """Compatibilidad temporal para instalaciones creadas sin migraciones."""
    _ensure_column("puestos", "ubicacion", "ubicacion VARCHAR(300)")
    _ensure_column("puestos", "salario_min", "salario_min FLOAT")
    _ensure_column("puestos", "salario_max", "salario_max FLOAT")
    _ensure_column("puestos", "moneda", "moneda VARCHAR(10) NOT NULL DEFAULT 'PEN'")
    _ensure_column(
        "puestos",
        "tipo_contrato",
        "tipo_contrato VARCHAR(50) NOT NULL DEFAULT 'tiempo_completo'",
    )
    _ensure_column(
        "puestos",
        "fecha_publicacion",
        "fecha_publicacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
    )
    _ensure_column("puestos", "fecha_cierre", "fecha_cierre TIMESTAMP")
    _ensure_column("cuentas", "telefono", "telefono VARCHAR(50)")
    _ensure_column("cuentas", "ciudad", "ciudad VARCHAR(100)")
    _ensure_column("cuentas", "foto_url", "foto_url TEXT")
    _ensure_column("cuentas", "perfil", "perfil TEXT")
    _ensure_column(
        "postulaciones",
        "documentos_adjuntos",
        "documentos_adjuntos JSON NOT NULL DEFAULT '[]'",
    )
    _ensure_column("hitos", "tipo_evento", "tipo_evento VARCHAR(40)")
    _ensure_column("hitos", "estado_anterior", "estado_anterior VARCHAR(30)")
    _ensure_column("hitos", "estado_nuevo", "estado_nuevo VARCHAR(30)")
    _ensure_column(
        "contactos_postulacion",
        "remitente_rol",
        "remitente_rol VARCHAR(20) NOT NULL DEFAULT 'empresa'",
    )
    _ensure_column(
        "contactos_postulacion",
        "leido",
        "leido BOOLEAN NOT NULL DEFAULT FALSE",
    )
    _normalizar_estados_legacy()


def _normalizar_estados_legacy() -> None:
    """Migra aliases historicos sin exponer dos vocabularios en la API."""
    inspector = inspect(engine)
    if "postulaciones" not in inspector.get_table_names():
        return

    with engine.begin() as connection:
        aceptadas = connection.execute(
            text(
                "UPDATE postulaciones SET estado = 'ACEPTADO' "
                "WHERE LOWER(estado) = 'oferta'"
            )
        ).rowcount
        rechazadas = connection.execute(
            text(
                "UPDATE postulaciones SET estado = 'RECHAZADO' "
                "WHERE LOWER(estado) = 'rechazo'"
            )
        ).rowcount

    if aceptadas or rechazadas:
        logger.info(
            "Estados legacy normalizados: %s aceptadas, %s rechazadas.",
            aceptadas,
            rechazadas,
        )


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        Base.metadata.create_all(bind=engine)
        _ensure_runtime_schema()
        logger.info("Esquema de base de datos listo.")
    except Exception:
        logger.exception("No se pudo preparar el esquema de base de datos.")
        raise
    yield


docs_enabled = settings.DEBUG or settings.ENABLE_SWAGGER
app = FastAPI(
    title="LookUp API",
    description="API compartida para postulantes y empresas de LookUp.",
    version="1.1.0",
    docs_url="/docs" if docs_enabled else None,
    redoc_url="/redoc" if docs_enabled else None,
    openapi_url="/openapi.json" if docs_enabled else None,
    swagger_ui_parameters={"defaultModelsExpandDepth": -1},
    lifespan=lifespan,
)

allow_credentials = "*" not in settings.CORS_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(postulacion_router, prefix="/api")
app.include_router(contacto_router, prefix="/api")
app.include_router(metrica_router, prefix="/api")
app.include_router(puesto_router, prefix="/api")
app.include_router(iam_router, prefix="/api")
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")


@app.get("/", tags=["Sistema"])
async def root():
    return {
        "message": "LookUp API disponible",
        "version": "1.1.0",
        "environment": settings.ENVIRONMENT,
    }
