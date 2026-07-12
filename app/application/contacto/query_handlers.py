from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.domain.common import Query, QueryHandler
from app.domain.contacto.repositories import ContactoRepository


@dataclass
class ObtenerContactosPostulacionQuery(Query):
    """Query para obtener contactos asociados a una postulación"""
    postulacion_id: UUID


class ObtenerContactosPostulacionQueryHandler(QueryHandler):
    """
    Manejador de consulta para obtener contactos de una postulación
    """
    
    def __init__(self, contacto_repository: ContactoRepository):
        self.contacto_repository = contacto_repository
    
    def handle(self, query: ObtenerContactosPostulacionQuery) -> List[Dict[str, Any]]:
        """
        Maneja la consulta de contactos por postulación
        """
        contactos = self.contacto_repository.obtener_por_postulacion(query.postulacion_id)
        
        # Construir respuesta
        resultado = []
        for contacto_aggregate in contactos:
            contacto = contacto_aggregate.contacto_postulacion
            
            # Obtener el último feedback si existe
            ultimo_feedback = None
            if contacto_aggregate.lista_feedback:
                feedback = contacto_aggregate.lista_feedback[-1]
                ultimo_feedback = {
                    "tipo": feedback.tipo.value,
                    "mensaje": feedback.mensaje_texto,
                    "motivo_rechazo": feedback.motivo_rechazo
                }

            feedbacks = [
                {
                    "tipo": feedback.tipo.value,
                    "mensaje": feedback.mensaje_texto,
                    "motivo_rechazo": feedback.motivo_rechazo
                }
                for feedback in contacto_aggregate.lista_feedback
            ]
            
            resultado.append({
                "contacto_id": str(contacto.contacto_id),
                "postulacion_id": str(contacto.postulacion_id),
                "empresa_id": str(contacto.empresa_id),
                "cuenta_id": str(contacto.cuenta_id),
                "tipo_mensaje": contacto.tipo_mensaje.value,
                "remitente_rol": contacto.remitente_rol,
                "motivo_rechazo": contacto.motivo_rechazo,
                "leido": contacto.leido,
                "fecha_hora": contacto.fecha_hora.isoformat(),
                "ultimo_feedback": ultimo_feedback,
                "feedbacks": feedbacks
            })
        
        return resultado


@dataclass
class ObtenerContactoQuery(Query):
    """Query para obtener detalles de un contacto específico"""
    contacto_id: UUID


class ObtenerContactoQueryHandler(QueryHandler):
    """
    Manejador de consulta para obtener un contacto por ID
    """
    
    def __init__(self, contacto_repository: ContactoRepository):
        self.contacto_repository = contacto_repository
    
    def handle(self, query: ObtenerContactoQuery) -> Optional[Dict[str, Any]]:
        """
        Maneja la consulta de contacto por ID
        """
        contacto_aggregate = self.contacto_repository.obtener_por_id(query.contacto_id)
        
        if not contacto_aggregate:
            return None
        
        contacto = contacto_aggregate.contacto_postulacion
        
        # Construir respuesta con todos los feedbacks
        return {
            "contacto_id": str(contacto.contacto_id),
            "postulacion_id": str(contacto.postulacion_id),
            "empresa_id": str(contacto.empresa_id),
            "cuenta_id": str(contacto.cuenta_id),
            "tipo_mensaje": contacto.tipo_mensaje.value,
            "remitente_rol": contacto.remitente_rol,
            "motivo_rechazo": contacto.motivo_rechazo,
            "leido": contacto.leido,
            "fecha_hora": contacto.fecha_hora.isoformat(),
            "feedbacks": [
                {
                    "tipo": feedback.tipo.value,
                    "mensaje": feedback.mensaje_texto,
                    "motivo_rechazo": feedback.motivo_rechazo
                }
                for feedback in contacto_aggregate.lista_feedback
            ]
        }
