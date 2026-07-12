from typing import List, Optional
from uuid import UUID, uuid4

from app.domain.contacto.entities import (
    ContactoPostulacion, Feedback, ContactoAggregate, 
    TipoFeedbackEnum, TipoMensajeEnum
)
from app.domain.contacto.repositories import ContactoRepository
from app.infrastructure.database.connection import SessionLocal
from app.infrastructure.contacto.models import ContactoPostulacionModel, FeedbackModel


class ContactoRepositoryImpl(ContactoRepository):
    def guardar(self, contacto_aggregate: ContactoAggregate) -> UUID:

        db = SessionLocal()
        try:
            contacto = contacto_aggregate.contacto_postulacion
            contacto_id = contacto.contacto_id
            
            contacto_db = db.query(ContactoPostulacionModel).filter(
                ContactoPostulacionModel.id == str(contacto_id)
            ).first()
            
            if not contacto_db:
                contacto_db = ContactoPostulacionModel(
                    id=str(contacto_id),
                    postulacion_id=str(contacto.postulacion_id),
                    empresa_id=str(contacto.empresa_id),
                    cuenta_id=str(contacto.cuenta_id),
                    tipo_mensaje=contacto.tipo_mensaje.value,
                    remitente_rol=contacto.remitente_rol,
                    motivo_rechazo=contacto.motivo_rechazo,
                    fecha_hora=contacto.fecha_hora,
                    leido=contacto.leido,
                )
                db.add(contacto_db)
            else:
                contacto_db.tipo_mensaje = contacto.tipo_mensaje.value
                contacto_db.remitente_rol = contacto.remitente_rol
                contacto_db.motivo_rechazo = contacto.motivo_rechazo
                contacto_db.leido = contacto.leido
            
            db.query(FeedbackModel).filter(
                FeedbackModel.contacto_id == str(contacto_id)
            ).delete()
            

            for feedback in contacto_aggregate.lista_feedback:
                feedback_id = uuid4() 
                feedback_db = FeedbackModel(
                    id=str(feedback_id),
                    contacto_id=str(contacto_id),
                    tipo=feedback.tipo.value,
                    mensaje_texto=feedback.mensaje_texto,
                    motivo_rechazo=feedback.motivo_rechazo
                )
                db.add(feedback_db)
            
            db.commit()
            return contacto_id
            
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    def obtener_por_id(self, contacto_id: UUID) -> Optional[ContactoAggregate]:
        """Recupera un contacto por su i"""
        db = SessionLocal()
        try:
            contacto_db = db.query(ContactoPostulacionModel).filter(
                ContactoPostulacionModel.id == str(contacto_id)
            ).first()
            
            if not contacto_db:
                return None
            
            contacto = ContactoPostulacion(
                contacto_id=UUID(contacto_db.id),
                postulacion_id=UUID(contacto_db.postulacion_id),
                empresa_id=UUID(contacto_db.empresa_id),
                cuenta_id=UUID(contacto_db.cuenta_id),
                tipo_mensaje=TipoMensajeEnum(contacto_db.tipo_mensaje),
                remitente_rol=getattr(contacto_db, "remitente_rol", None) or "empresa",
                motivo_rechazo=contacto_db.motivo_rechazo,
                fecha_hora=contacto_db.fecha_hora,
                leido=bool(contacto_db.leido),
            )
            
            lista_feedback = []
            for feedback_db in contacto_db.feedbacks:
                feedback = Feedback(
                    tipo=TipoFeedbackEnum(feedback_db.tipo),
                    mensaje_texto=feedback_db.mensaje_texto,
                    motivo_rechazo=feedback_db.motivo_rechazo
                )
                lista_feedback.append(feedback)
            
            contacto_aggregate = ContactoAggregate(
                contacto_postulacion=contacto,
                lista_feedback=lista_feedback
            )
            
            return contacto_aggregate
            
        finally:
            db.close()
    
    def obtener_por_postulacion(self, postulacion_id: UUID) -> List[ContactoAggregate]:
        """Recupera todos los contactos asociados a una postulación"""
        db = SessionLocal()
        try:
            contactos_db = db.query(ContactoPostulacionModel).filter(
                ContactoPostulacionModel.postulacion_id == str(postulacion_id)
            ).order_by(ContactoPostulacionModel.fecha_hora.asc()).all()
            
            resultado = []
            for contacto_db in contactos_db:
                #### Obtener cada contacto completo
                contacto_aggregate = self.obtener_por_id(UUID(contacto_db.id))
                if contacto_aggregate:
                    resultado.append(contacto_aggregate)
            
            return resultado
            
        finally:
            db.close()
