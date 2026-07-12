from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from app.domain.common import Command, CommandHandler
from app.domain.contacto.entities import (
    ContactoPostulacion, Feedback, ContactoAggregate, 
    TipoFeedbackEnum, TipoMensajeEnum
)
from app.domain.contacto.repositories import ContactoRepository


@dataclass
class EnviarFeedbackCommand(Command):
    """Comando para enviar feedback a un postulante"""
    postulacion_id: UUID
    empresa_id: UUID
    cuenta_id: UUID
    tipo_feedback: str
    mensaje_texto: str
    motivo_rechazo: Optional[str] = None


class EnviarFeedbackCommandHandler(CommandHandler):
    """
    Manejador del comando para enviar feedback a un postulante
    """
    
    def __init__(self, contacto_repository: ContactoRepository):
        self.contacto_repository = contacto_repository
    
    def handle(self, command: EnviarFeedbackCommand) -> UUID:
        """
        Maneja el comando de envío de feedback
        """
        try:
            # Convertir string a enum
            tipo_feedback_enum = TipoFeedbackEnum(command.tipo_feedback)
        except ValueError:
            raise ValueError(f"Tipo de feedback '{command.tipo_feedback}' no válido")
        
        # Crear el feedback como value object
        feedback = Feedback(
            tipo=tipo_feedback_enum,
            mensaje_texto=command.mensaje_texto,
            motivo_rechazo=command.motivo_rechazo
        )
        
        # Validar que el feedback es válido
        if not feedback.validar_motivo():
            raise ValueError("Se requiere motivo de rechazo para feedback de tipo 'rechazo'")
        
        # Crear contacto de postulación
        contacto = ContactoPostulacion(
            postulacion_id=command.postulacion_id,
            empresa_id=command.empresa_id,
            cuenta_id=command.cuenta_id,
            tipo_mensaje=TipoMensajeEnum.FEEDBACK,
            remitente_rol="empresa"
        )
        
        # Crear agregado
        contacto_aggregate = ContactoAggregate(
            contacto_postulacion=contacto
        )
        
        # Procesar el feedback
        contacto_aggregate.procesar_feedback(feedback)
        
        # Actualizar el estado de la postulación según el feedback
        contacto_aggregate.actualizar_estado_postulacion()
        
        # Guardar en repositorio
        contacto_id = self.contacto_repository.guardar(contacto_aggregate)
        
        return contacto_id
