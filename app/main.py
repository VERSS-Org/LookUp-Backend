import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi

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


try:
    if engine is not None:
        logger.info("Creando tablas en la base de datos...")
        Base.metadata.create_all(bind=engine)
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
