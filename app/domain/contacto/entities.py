from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4

from app.domain.common import AggregateRoot


class TipoFeedbackEnum(str, Enum):
    """Valores posibles para el tipo de feedback"""
    APROBACION = "aprobacion"
    RECHAZO = "rechazo"
    COMENTARIO = "comentario"
    OTRO = "otro"


@dataclass(frozen=True)
class Feedback:
    """Value Object que representa el contenido del feedback enviado al postulante"""
    tipo: TipoFeedbackEnum
    mensaje_texto: str
    motivo_rechazo: Optional[str] = None
    
    def validar_motivo(self) -> bool:
        """
        Valida que el motivo de rechazo esté presente cuando el tipo es rechazo
        """
        if self.tipo == TipoFeedbackEnum.RECHAZO:
            return self.motivo_rechazo is not None and self.motivo_rechazo.strip() != ""
        return True
    
    def formatear_mensaje(self) -> str:
        """
        Devuelve un mensaje formateado según el tipo de feedback
        """
        if self.tipo == TipoFeedbackEnum.APROBACION:
            return f"¡Felicitaciones! {self.mensaje_texto}"
        elif self.tipo == TipoFeedbackEnum.RECHAZO:
            return f"Lo sentimos. {self.mensaje_texto}. Motivo: {self.motivo_rechazo}"
        else:  # INFORMATIVO
            return self.mensaje_texto


class TipoMensajeEnum(str, Enum):
    """Valores posibles para el tipo de mensaje de contacto"""
    SOLICITUD_INFO = "solicitud_info"
    FEEDBACK = "feedback"
    ACTUALIZACION = "actualizacion"


@dataclass
class ContactoPostulacion:
    """Entity que representa la interacción entre la empresa y el postulante"""
    contacto_id: UUID = field(default_factory=uuid4)
    postulacion_id: UUID = None
    empresa_id: UUID = None
    cuenta_id: UUID = None  # ID de la cuenta del candidato
    tipo_mensaje: TipoMensajeEnum = TipoMensajeEnum.FEEDBACK
    motivo_rechazo: Optional[str] = None
    fecha_hora: datetime = field(default_factory=datetime.now)
    
    def asociar_feedback(self, feedback: Feedback) -> bool:
        """Asocia un feedback al contacto"""
        if not feedback.validar_motivo():
            return False
        
        if feedback.tipo == TipoFeedbackEnum.RECHAZO:
            self.motivo_rechazo = feedback.motivo_rechazo
        
        return True
    
    def marcar_como_aceptado(self) -> None:
        """Marca el contacto como aceptado"""
        self.tipo_mensaje = TipoMensajeEnum.FEEDBACK
        self.motivo_rechazo = None
    
    def marcar_como_rechazado(self) -> None:
        """Marca el contacto como rechazado"""
        self.tipo_mensaje = TipoMensajeEnum.FEEDBACK
        if not self.motivo_rechazo:
            self.motivo_rechazo = "Sin especificar"


@dataclass
class ContactoAggregate(AggregateRoot):
    """
    Aggregate que gestiona las interacciones de la empresa hacia el postulante
    """
    contacto_postulacion: ContactoPostulacion
    lista_feedback: List[Feedback] = field(default_factory=list)
    
    def procesar_feedback(self, feedback: Feedback) -> bool:
        """
        Procesa un nuevo feedback y lo asocia al contacto
        """
        if not self.contacto_postulacion.asociar_feedback(feedback):
            return False
        
        self.lista_feedback.append(feedback)
        
        # Evento de dominio
        self.add_event(FeedbackEnviado(
            self.contacto_postulacion.contacto_id,
            self.contacto_postulacion.postulacion_id,
            feedback.tipo
        ))
        return True
    
    def actualizar_estado_postulacion(self) -> None:
        """
        Actualiza el estado de la postulación según el último feedback
        Este método emitiría eventos para que el bounded context de postulación 
        actualice el estado correspondiente
        """
        if not self.lista_feedback:
            return
        
        ultimo_feedback = self.lista_feedback[-1]
        
        if ultimo_feedback.tipo == TipoFeedbackEnum.APROBACION:
            # Emitir evento para actualizar postulación a OFERTA
            self.add_event(SolicitudCambioEstadoPostulacion(
                self.contacto_postulacion.postulacion_id,
                "oferta"
            ))
            self.contacto_postulacion.marcar_como_aceptado()
        
        elif ultimo_feedback.tipo == TipoFeedbackEnum.RECHAZO:
            # Emitir evento para actualizar postulación a RECHAZO
            self.add_event(SolicitudCambioEstadoPostulacion(
                self.contacto_postulacion.postulacion_id,
                "rechazado"
            ))
            self.contacto_postulacion.marcar_como_rechazado()


# Eventos de dominio
@dataclass
class FeedbackEnviado:
    """Evento que se emite cuando se envía un feedback a un postulante"""
    contacto_id: UUID
    postulacion_id: UUID
    tipo_feedback: TipoFeedbackEnum


@dataclass
class SolicitudCambioEstadoPostulacion:
    """
    Evento que solicita al bounded context de postulación que cambie el estado
    """
    postulacion_id: UUID
    nuevo_estado: str
