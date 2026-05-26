from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
from uuid import UUID


# Enums para schemas
class TipoContactoEnum(str, Enum):
    EMAIL = "email"
    LLAMADA = "llamada"
    ENTREVISTA = "entrevista"
    OTRO = "otro"


class TipoFeedbackEnum(str, Enum):
    APROBACION = "aprobacion"
    RECHAZO = "rechazo"
    COMENTARIO = "comentario"
    OTRO = "otro"


# Schemas para Contacto
class ContactoCreate(BaseModel):
    postulacion_id: str
    tipo_contacto: TipoContactoEnum
    contenido: str
    fecha_contacto: Optional[datetime] = None


class FeedbackResumen(BaseModel):
    tipo: str
    mensaje: Optional[str] = None
    motivo_rechazo: Optional[str] = None


class ContactoResponse(BaseModel):
    contacto_id: str
    postulacion_id: str
    empresa_id: str
    cuenta_id: str
    tipo_mensaje: str
    remitente_rol: str = "empresa"
    motivo_rechazo: Optional[str] = None
    fecha_hora: datetime
    ultimo_feedback: Optional[FeedbackResumen] = None
    feedbacks: List[FeedbackResumen] = Field(default_factory=list)


class ContactoUpdate(BaseModel):
    tipo_contacto: Optional[TipoContactoEnum] = None
    contenido: Optional[str] = None
    leido: Optional[bool] = None


# Schemas para Feedback
class FeedbackCreate(BaseModel):
    postulacion_id: str
    empresa_id: str
    cuenta_id: str
    tipo_feedback: TipoFeedbackEnum
    mensaje_texto: Optional[str] = None
    motivo_rechazo: Optional[str] = None


class MensajeContactoCreate(BaseModel):
    postulacion_id: str
    mensaje_texto: str


class FeedbackResponse(BaseModel):
    feedback_id: str
    postulacion_id: str
    tipo_feedback: str
    mensaje: Optional[str] = None
    fecha_envio: datetime
