from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import datetime
from enum import Enum


# Enums para schemas
class TipoContactoEnum(str, Enum):
    SOLICITUD_INFO = "solicitud_info"
    FEEDBACK = "feedback"
    ACTUALIZACION = "actualizacion"


class TipoFeedbackEnum(str, Enum):
    APROBACION = "aprobacion"
    RECHAZO = "rechazo"
    COMENTARIO = "comentario"
    OTRO = "otro"


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
    leido: bool = False
    ultimo_feedback: Optional[FeedbackResumen] = None
    feedbacks: List[FeedbackResumen] = Field(default_factory=list)


# Schemas para Feedback
class FeedbackCreate(BaseModel):
    postulacion_id: str
    empresa_id: str
    cuenta_id: str
    tipo_feedback: TipoFeedbackEnum
    mensaje_texto: str = Field(min_length=1, max_length=5000)
    motivo_rechazo: Optional[str] = Field(None, max_length=500)

    @field_validator("mensaje_texto")
    @classmethod
    def validar_mensaje(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("mensaje_texto no puede estar vacío")
        return value

    @model_validator(mode="after")
    def validar_rechazo(self):
        if self.tipo_feedback == TipoFeedbackEnum.RECHAZO:
            motivo = (self.motivo_rechazo or "").strip()
            if not motivo:
                raise ValueError("motivo_rechazo es requerido para un rechazo")
            self.motivo_rechazo = motivo
        return self


class MensajeContactoCreate(BaseModel):
    postulacion_id: str
    mensaje_texto: str = Field(min_length=1, max_length=5000)

    @field_validator("mensaje_texto")
    @classmethod
    def validar_mensaje(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("mensaje_texto no puede estar vacío")
        return value


class FeedbackResponse(BaseModel):
    feedback_id: str
    postulacion_id: str
    tipo_feedback: str
    mensaje: Optional[str] = None
    fecha_envio: datetime
