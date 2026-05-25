from typing import Dict, List, Optional, Any
from pydantic import BaseModel
from datetime import datetime
from enum import Enum
from uuid import UUID


# Enums para schemas
class EstadoPostulacionEnum(str, Enum):
    PENDIENTE = "pendiente"
    EN_REVISION = "en_revision"
    RECHAZADO = "rechazado"
    ACEPTADO = "aceptado"
    ENTREVISTA = "entrevista"
    OFERTA = "oferta"
    RECHAZO = "rechazo"


class EstadoPublicacionEnum(str, Enum):
    BORRADOR = "borrador"
    PUBLICADO = "publicado"
    CERRADO = "cerrado"


# Schemas para Postulación
class PostulacionCreate(BaseModel):
    candidato_id: str
    puesto_id: str
    documentos_adjuntos: Optional[List[Dict[str, Any]]] = None


class HitoResponse(BaseModel):
    hito_id: str
    fecha: datetime
    descripcion: str


class CandidatoInfoResponse(BaseModel):
    """Información del candidato para enriquecer postulación"""
    cuenta_id: str
    nombre_completo: str
    email: str
    carrera: Optional[str] = None
    telefono: Optional[str] = None
    ciudad: Optional[str] = None


class PuestoInfoResponse(BaseModel):
    """Información del puesto para enriquecer postulación"""
    puesto_id: str
    empresa_id: Optional[str] = None
    titulo: str
    descripcion: str
    ubicacion: str
    salario_min: Optional[float] = None
    salario_max: Optional[float] = None
    moneda: str = "MXN"
    tipo_contrato: str


class EmpresaInfoResponse(BaseModel):
    """Información de la empresa para enriquecer postulación"""
    empresa_id: str
    nombre: str
    email: str


class PostulacionResponse(BaseModel):
    postulacion_id: str
    candidato_id: str
    puesto_id: str
    fecha_postulacion: datetime
    estado: str
    documentos_adjuntos: List[Dict[str, Any]]
    hitos: List[HitoResponse]


class PostulacionEnriquecidaResponse(BaseModel):
    """Respuesta de postulación con información enriquecida de candidato, puesto y empresa"""
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


# Schemas para Puesto
class PuestoCreate(BaseModel):
    empresa_id: str
    titulo: str
    descripcion: str
    requisitos: List[str]
    fecha_inicio: Optional[str] = None
    fecha_fin: Optional[str] = None


class PuestoResponse(BaseModel):
    puesto_id: str
    empresa_id: str
    titulo: str
    descripcion: str
    requisitos: List[str]
    fecha_inicio: datetime
    fecha_fin: Optional[datetime] = None
    estado_publicacion: str
