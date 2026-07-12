from typing import Dict, List, Optional, Any
from pydantic import BaseModel, field_validator
from datetime import datetime
from enum import Enum

from app.domain.postulacion.entities import (
    ESTADOS_POSTULACION_CANONICOS,
    normalizar_estado_postulacion,
)


# Enums para schemas
class EstadoPostulacionEnum(str, Enum):
    PENDIENTE = "pendiente"
    EN_REVISION = "en_revision"
    RECHAZADO = "rechazado"
    ACEPTADO = "aceptado"
    ENTREVISTA = "entrevista"


# Schemas para Postulación
class PostulacionCreate(BaseModel):
    candidato_id: str
    puesto_id: str
    documentos_adjuntos: Optional[List[Dict[str, Any]]] = None


class HitoResponse(BaseModel):
    hito_id: str
    fecha: datetime
    descripcion: str
    tipo_evento: str = "hito"
    estado_anterior: Optional[str] = None
    estado_nuevo: Optional[str] = None


class EventoRecienteResponse(BaseModel):
    """Evento estructurado; ``descripcion`` se mantiene para clientes antiguos."""

    tipo: str
    tipo_evento: str
    titulo: Optional[str] = None
    descripcion: str
    fecha: datetime
    postulacion_id: str
    estado_anterior: Optional[str] = None
    estado_nuevo: Optional[str] = None


class CandidatoInfoResponse(BaseModel):
    """Información del postulante para enriquecer la postulación."""
    cuenta_id: str
    nombre_completo: str
    email: str
    carrera: Optional[str] = None
    telefono: Optional[str] = None
    ciudad: Optional[str] = None
    foto_url: Optional[str] = None


class PuestoInfoResponse(BaseModel):
    """Información de la vacante para enriquecer la postulación."""
    puesto_id: str
    empresa_id: Optional[str] = None
    titulo: str
    descripcion: str
    ubicacion: str
    salario_min: Optional[float] = None
    salario_max: Optional[float] = None
    moneda: str = "PEN"
    tipo_contrato: str


class EmpresaInfoResponse(BaseModel):
    """Información de la empresa para enriquecer postulación"""
    empresa_id: str
    nombre: str
    email: str
    foto_url: Optional[str] = None


class PostulacionResponse(BaseModel):
    postulacion_id: str
    candidato_id: str
    puesto_id: str
    fecha_postulacion: datetime
    estado: str
    documentos_adjuntos: List[Dict[str, Any]]
    hitos: List[HitoResponse]


class PostulacionEnriquecidaResponse(BaseModel):
    """Postulación enriquecida con datos del postulante, la vacante y la empresa."""
    postulacion_id: str
    fecha_postulacion: datetime
    estado: str
    documentos_adjuntos: List[Dict[str, Any]]
    hitos: List[HitoResponse]
    # Información enriquecida
    candidato: Optional[CandidatoInfoResponse] = None
    puesto: Optional[PuestoInfoResponse] = None
    empresa: Optional[EmpresaInfoResponse] = None


class EstadoUpdate(BaseModel):
    nuevo_estado: str

    @field_validator("nuevo_estado")
    @classmethod
    def validar_estado(cls, value: str) -> str:
        estado = normalizar_estado_postulacion(value)
        if estado not in ESTADOS_POSTULACION_CANONICOS:
            raise ValueError("Estado de postulación inválido")
        return estado
