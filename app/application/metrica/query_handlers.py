from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.domain.common import Query, QueryHandler
from app.domain.metrica.repositories import MetricaRepository


@dataclass
class ConsultarResumenMetricasQuery(Query):
    """Query para consultar el resumen de métricas de un postulante"""
    cuenta_id: UUID


class ConsultarResumenMetricasHandler(QueryHandler):
    """
    Manejador de consulta para obtener el resumen de métricas de un postulante
    """
    
    def __init__(self, metrica_repository: MetricaRepository):
        self.metrica_repository = metrica_repository
    
    def handle(self, query: ConsultarResumenMetricasQuery) -> Optional[Dict[str, Any]]:
        """
        Maneja la consulta de resumen de métricas
        
        Nota: Las métricas ahora se calculan en tiempo real basadas en el estado actual
        de las postulaciones en lugar de recuperarse de registros almacenados previamente.
        """
        # Calcular el agregado de métricas del postulante en tiempo real
        metrica_aggregate = self.metrica_repository.obtener_por_postulante(query.cuenta_id)
        
        if not metrica_aggregate:
            return None
        
        # Construir respuesta
        return {
            "cuenta_id": str(metrica_aggregate.metrica_registro.cuenta_id),
            "total_postulaciones": metrica_aggregate.metrica_registro.total_postulaciones,
            "total_entrevistas": metrica_aggregate.metrica_registro.total_entrevistas,
            "total_exitos": metrica_aggregate.metrica_registro.total_exitos,
            "total_rechazos": metrica_aggregate.metrica_registro.total_rechazos,
            "tasa_exito": metrica_aggregate.metrica_registro.tasa_exito
        }


@dataclass
class ListarLogrosQuery(Query):
    """Query para listar los logros de un postulante"""
    cuenta_id: UUID


class ListarLogrosHandler(QueryHandler):
    """
    Manejador de consulta para listar los logros de un postulante
    """
    
    def __init__(self, metrica_repository: MetricaRepository):
        self.metrica_repository = metrica_repository
    
    def handle(self, query: ListarLogrosQuery) -> List[Dict[str, Any]]:
        """
        Maneja la consulta de logros
        """
        # Recuperar el agregado de métricas del postulante
        metrica_aggregate = self.metrica_repository.obtener_por_postulante(query.cuenta_id)
        
        if not metrica_aggregate:
            return []
        
        # Construir respuesta
        return [
            {
                "id_logro": str(logro.id_logro),
                "nombre_logro": logro.nombre_logro,
                "umbral": logro.umbral,
                "fecha_obtencion": logro.fecha_obtencion.isoformat()
            }
            for logro in metrica_aggregate.lista_logros
        ]


@dataclass
class ContadorAceptacionesQuery(Query):
    """
    Query para consultar el contador de postulaciones aceptadas.
    """
    postulante_id: UUID


class ContadorAceptacionesQueryHandler(QueryHandler):
    """
    Manejador para consultar el contador de postulaciones aceptadas.
    """
    
    def __init__(self, metrica_repository: MetricaRepository):
        self.metrica_repository = metrica_repository
    
    def handle(self, query: ContadorAceptacionesQuery) -> Dict[str, Any]:
        """
        Maneja la consulta del contador de aceptaciones.
        
        El contador se calcula desde las postulaciones en estado `aceptado`.
        """
        metrica = self.metrica_repository.obtener_por_postulante(
            query.postulante_id
        )
        total_aceptaciones = (
            metrica.metrica_registro.total_exitos if metrica else 0
        )
        
        return {
            "postulante_id": str(query.postulante_id),
            "total_aceptaciones": total_aceptaciones
        }


@dataclass
class ContadorEntrevistasQuery(Query):
    """
    Query para consultar el contador de entrevistas obtenidas
    US22: Contador de entrevistas obtenidas
    """
    postulante_id: UUID


class ContadorEntrevistasQueryHandler(QueryHandler):
    """
    Manejador para consultar el contador de entrevistas obtenidas
    """
    
    def __init__(self, metrica_repository: MetricaRepository):
        self.metrica_repository = metrica_repository
    
    def handle(self, query: ContadorEntrevistasQuery) -> Dict[str, Any]:
        """
        Maneja la consulta del contador de entrevistas
        
        Nota: El contador se calcula en tiempo real contando las postulaciones
        que actualmente tienen estado 'entrevista' en lugar de recuperar un valor almacenado.
        """
        metrica = self.metrica_repository.obtener_por_postulante(
            query.postulante_id
        )
        total_entrevistas = (
            metrica.metrica_registro.total_entrevistas if metrica else 0
        )
        
        return {
            "postulante_id": str(query.postulante_id),
            "total_entrevistas": total_entrevistas
        }


@dataclass
class ContadorRechazosQuery(Query):
    """
    Query para consultar el contador de rechazos acumulados
    US24: Contador de rechazos acumulados
    """
    postulante_id: UUID


class ContadorRechazosQueryHandler(QueryHandler):
    """
    Manejador para consultar el contador de rechazos acumulados
    """
    
    def __init__(self, metrica_repository: MetricaRepository):
        self.metrica_repository = metrica_repository
    
    def handle(self, query: ContadorRechazosQuery) -> Dict[str, Any]:
        """
        Maneja la consulta del contador de rechazos
        
        Nota: El contador se calcula en tiempo real contando las postulaciones
        que actualmente tienen estado 'rechazado' en lugar de recuperar un valor almacenado.
        """
        metrica = self.metrica_repository.obtener_por_postulante(
            query.postulante_id
        )
        total_rechazos = (
            metrica.metrica_registro.total_rechazos if metrica else 0
        )
        
        return {
            "postulante_id": str(query.postulante_id),
            "total_rechazos": total_rechazos
        }
