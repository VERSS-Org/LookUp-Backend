import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from sqlalchemy import inspect, text

from app.infrastructure.database.connection import engine, Base
from app.interface.api.postulacion.router import router as postulacion_router
from app.interface.api.contacto.router import router as contacto_router
from app.interface.api.metrica.router import router as metrica_router
from app.interface.api.puesto.router import router as puesto_router
from app.interface.api.iam.router import router as iam_router
from app.config import settings


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def _ensure_column(table_name: str, column_name: str, ddl: str) -> None:
    if engine is None:
        return

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
    # create_all no altera tablas existentes; estas columnas son necesarias para
    # instalaciones que nacieron con el esquema inicial del proyecto.
    _ensure_column("puestos", "ubicacion", "ubicacion VARCHAR(300)")
    _ensure_column("puestos", "salario_min", "salario_min FLOAT")
    _ensure_column("puestos", "salario_max", "salario_max FLOAT")
    _ensure_column("puestos", "moneda", "moneda VARCHAR(10) NOT NULL DEFAULT 'MXN'")
    _ensure_column("puestos", "tipo_contrato", "tipo_contrato VARCHAR(50) NOT NULL DEFAULT 'tiempo_completo'")
    _ensure_column("puestos", "fecha_publicacion", "fecha_publicacion TIMESTAMP NOT NULL DEFAULT NOW()")
    _ensure_column("puestos", "fecha_cierre", "fecha_cierre TIMESTAMP")
    _ensure_column("cuentas", "foto_url", "foto_url TEXT")
    _ensure_column("contactos_postulacion", "remitente_rol", "remitente_rol VARCHAR(20) NOT NULL DEFAULT 'empresa'")


try:
    if engine is not None:
        logger.info("Creando tablas en la base de datos...")
        Base.metadata.create_all(bind=engine)
        _ensure_runtime_schema()
        logger.info("Tablas creadas exitosamente.")
    else:
        logger.warning("Motor de base de datos no disponible, no se pueden crear tablas.")
except Exception as e:
    logger.error(f"Error al crear tablas: {e}")


app = FastAPI(
    title="API de Gestión de Postulaciones",
    description="API REST con FastAPI y PostgreSQL implementando Domain-Driven Design",
    version="1.0.0",
    docs_url="/docs",  
    redoc_url="/redoc", 
    swagger_ui_parameters={"defaultModelsExpandDepth": -1}
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(postulacion_router, prefix="/api")
app.include_router(contacto_router, prefix="/api")
app.include_router(metrica_router, prefix="/api")
app.include_router(puesto_router, prefix="/api")
app.include_router(iam_router, prefix="/api")

@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "Bienvenido a la API de Gestión de Postulaciones",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT
    }


@app.get("/openapi.json", include_in_schema=False)
async def get_open_api_endpoint():
    return get_openapi(
        title="API de Gestión de Postulaciones", 
        version="1.0.0",
        description="API REST con FastAPI y PostgreSQL implementando Domain-Driven Design",
        routes=app.routes,
        tags=[
            {"name": "Root", "description": "Endpoints principales de la aplicación"},
            {"name": "Postulación", "description": "Gestión de postulaciones de candidatos a ofertas laborales"},
            {"name": "Contacto", "description": "Gestión de contactos y comunicaciones"},
            {"name": "Métricas", "description": "Análisis y métricas de postulaciones"},
            {"name": "Puesto", "description": "Gestión de puestos de trabajo"},
            {"name": "IAM", "description": "Gestión de identidad y acceso con autenticación JWT"}
        ]
    )


@app.get("/docs", include_in_schema=False)
async def get_documentation():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="API de Gestión de Postulaciones - Documentación",
        swagger_favicon_url="",
        swagger_ui_parameters={
            "docExpansion": "list",
            "defaultModelsExpandDepth": -1,
            "deepLinking": True,
            "displayRequestDuration": True,
            "filter": True
        }
    )
# Updated
