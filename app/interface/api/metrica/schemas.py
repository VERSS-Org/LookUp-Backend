from pydantic import BaseModel
from datetime import datetime


# Schemas para Métricas (calculadas en tiempo real)
class MetricaResumenResponse(BaseModel):
    """
    Esquema para respuesta de resumen de métricas
    Representa métricas calculadas en tiempo real, no almacenadas
    """
    cuenta_id: str
    total_postulaciones: int
    total_en_revision: int
    total_entrevistas: int
    total_exitos: int
    total_rechazos: int
    tasa_exito: float


class LogroResponse(BaseModel):
    """
    Esquema para respuesta de logros conseguidos
    """
    id_logro: str
    nombre_logro: str
    umbral: int
    fecha_obtencion: datetime


class ContadorResponse(BaseModel):
    """
    Esquema para respuesta de contadores específicos
    """
    postulante_id: str
    total: int  # Valor genérico que representa cualquier contador
