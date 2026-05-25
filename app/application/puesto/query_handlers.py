from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.domain.common import Query, QueryHandler
from app.domain.puesto.entities import EstadoPuestoEnum
from app.domain.puesto.repositories import PuestoRepository


@dataclass
class ObtenerPuestoQuery(Query):
    """Query para obtener un puesto por ID"""
    puesto_id: UUID


class ObtenerPuestoQueryHandler(QueryHandler):
    """
    Manejador de consulta para obtener un puesto por ID
    """
    
    def __init__(self, puesto_repository: PuestoRepository):
        self.puesto_repository = puesto_repository
    
    def handle(self, query: ObtenerPuestoQuery) -> Optional[Dict[str, Any]]:
        """
        Maneja la consulta de puesto por ID
        """
        # Recuperar el puesto
        puesto_aggregate = self.puesto_repository.obtener_por_id(query.puesto_id)
        
        if not puesto_aggregate:
            return None
        
        # Obtener valores de enum o strings
        tipo_contrato_value = (puesto_aggregate.puesto.tipo_contrato.value 
                              if hasattr(puesto_aggregate.puesto.tipo_contrato, 'value') 
                              else puesto_aggregate.puesto.tipo_contrato)
        
        estado_value = (puesto_aggregate.puesto.estado.value 
                       if hasattr(puesto_aggregate.puesto.estado, 'value') 
                       else puesto_aggregate.puesto.estado)
        
        # Construir respuesta
        return {
            "puesto_id": str(puesto_aggregate.puesto.puesto_id),
            "empresa_id": str(puesto_aggregate.puesto.empresa_id),
            "titulo": puesto_aggregate.puesto.titulo,
            "descripcion": puesto_aggregate.puesto.descripcion,
            "ubicacion": puesto_aggregate.puesto.ubicacion,
            "salario_min": puesto_aggregate.puesto.salario_min,
            "salario_max": puesto_aggregate.puesto.salario_max,
            "moneda": puesto_aggregate.puesto.moneda,
            "tipo_contrato": tipo_contrato_value,
            "fecha_publicacion": puesto_aggregate.puesto.fecha_publicacion.isoformat(),
            "fecha_cierre": puesto_aggregate.puesto.fecha_cierre.isoformat() if puesto_aggregate.puesto.fecha_cierre else None,
            "estado": estado_value,
            "requisitos": [
                {
                    "tipo": req.tipo,
                    "descripcion": req.descripcion,
                    "es_obligatorio": req.es_obligatorio
                }
                for req in puesto_aggregate.requisitos
            ]
        }


@dataclass
class ListarPuestosQuery(Query):
    """Query para listar puestos con filtros"""
    empresa_id: Optional[UUID] = None
    estado: Optional[EstadoPuestoEnum] = None


class ListarPuestosQueryHandler(QueryHandler):
    """
    Manejador de consulta para listar puestos con filtros
    """
    
    def __init__(self, puesto_repository: PuestoRepository):
        self.puesto_repository = puesto_repository
    
    def handle(self, query: ListarPuestosQuery) -> List[Dict[str, Any]]:
        """
        Maneja la consulta de listado de puestos
        """
        if query.empresa_id:
            # Filtrar por empresa
            puestos = self.puesto_repository.listar_por_empresa(query.empresa_id)
        elif query.estado:
            # Filtrar por estado
            puestos = self.puesto_repository.listar_por_estado(query.estado.value)
        else:
            # Listar todos
            puestos = self.puesto_repository.listar_todos()

        if query.empresa_id and query.estado:
            puestos = [
                puesto for puesto in puestos
                if (
                    puesto.puesto.estado.value
                    if hasattr(puesto.puesto.estado, 'value')
                    else puesto.puesto.estado
                ) == query.estado.value
            ]
        
        # Construir respuesta resumida
        resultado = []
        for agg in puestos:
            tipo_contrato_value = (agg.puesto.tipo_contrato.value 
                                  if hasattr(agg.puesto.tipo_contrato, 'value') 
                                  else agg.puesto.tipo_contrato)
            
            estado_value = (agg.puesto.estado.value 
                           if hasattr(agg.puesto.estado, 'value') 
                           else agg.puesto.estado)
            
            resultado.append({
                "puesto_id": str(agg.puesto.puesto_id),
                "empresa_id": str(agg.puesto.empresa_id),
                "titulo": agg.puesto.titulo,
                "descripcion": agg.puesto.descripcion,
                "ubicacion": agg.puesto.ubicacion,
                "salario_min": agg.puesto.salario_min,
                "salario_max": agg.puesto.salario_max,
                "moneda": agg.puesto.moneda,
                "tipo_contrato": tipo_contrato_value,
                "fecha_publicacion": agg.puesto.fecha_publicacion.isoformat(),
                "fecha_cierre": agg.puesto.fecha_cierre.isoformat() if agg.puesto.fecha_cierre else None,
                "estado": estado_value,
                "requisitos": [
                    {
                        "tipo": req.tipo,
                        "descripcion": req.descripcion,
                        "es_obligatorio": req.es_obligatorio
                    }
                    for req in agg.requisitos
                ]
            })
        
        return resultado
