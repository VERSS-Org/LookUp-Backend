from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.domain.common import Command, CommandHandler
from app.domain.puesto.entities import (
    Puesto, PuestoAggregate, EstadoPuestoEnum, TipoContratoEnum,
    PuestoCreado, PuestoCerrado, PuestoActualizado,
    validar_tipo_contrato_escritura,
)
from app.domain.puesto.repositories import PuestoRepository


@dataclass
class CrearPuestoCommand(Command):
    """Comando para crear un nuevo puesto"""
    empresa_id: UUID
    titulo: str
    descripcion: str
    ubicacion: str
    salario_min: Optional[float] = None
    salario_max: Optional[float] = None
    moneda: str = "PEN"
    tipo_contrato: TipoContratoEnum = TipoContratoEnum.TIEMPO_COMPLETO
    requisitos: List[Dict[str, Any]] = None


class CrearPuestoHandler(CommandHandler):
    """
    Manejador del comando para crear un puesto
    """
    
    def __init__(self, puesto_repository: PuestoRepository):
        self.puesto_repository = puesto_repository
    
    def handle(self, command: CrearPuestoCommand) -> Dict[str, Any]:
        """
        Maneja el comando para crear un puesto
        """
        validar_tipo_contrato_escritura(command.tipo_contrato)

        # Crear la entidad Puesto
        puesto = Puesto(
            empresa_id=command.empresa_id,
            titulo=command.titulo,
            descripcion=command.descripcion,
            ubicacion=command.ubicacion,
            salario_min=command.salario_min,
            salario_max=command.salario_max,
            moneda=command.moneda,
            tipo_contrato=command.tipo_contrato
        )
        
        # Crear el agregado
        puesto_aggregate = PuestoAggregate(puesto=puesto)
        
        # Agregar requisitos si existen
        if command.requisitos:
            puesto_aggregate.actualizar_requisitos(command.requisitos)
        
        # Guardar en el repositorio
        puesto_id = self.puesto_repository.guardar(puesto_aggregate)
        
        # Emitir evento
        puesto_aggregate.add_event(PuestoCreado(puesto_id, command.empresa_id))
        
        # Devolver respuesta
        return {
            "puesto_id": str(puesto.puesto_id),
            "empresa_id": str(puesto.empresa_id),
            "titulo": puesto.titulo,
            "descripcion": puesto.descripcion,
            "ubicacion": puesto.ubicacion,
            "salario_min": puesto.salario_min,
            "salario_max": puesto.salario_max,
            "moneda": puesto.moneda,
            "tipo_contrato": puesto.tipo_contrato.value,
            "fecha_publicacion": puesto.fecha_publicacion.isoformat(),
            "estado": puesto.estado.value,
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
class ActualizarPuestoCommand(Command):
    """Comando para actualizar un puesto existente"""
    puesto_id: UUID
    titulo: Optional[str] = None
    descripcion: Optional[str] = None
    ubicacion: Optional[str] = None
    salario_min: Optional[float] = None
    salario_max: Optional[float] = None
    actualizar_salario_min: bool = False
    actualizar_salario_max: bool = False
    moneda: Optional[str] = None
    tipo_contrato: Optional[TipoContratoEnum] = None
    requisitos: Optional[List[Dict[str, Any]]] = None


class ActualizarPuestoHandler(CommandHandler):
    """
    Manejador del comando para actualizar un puesto
    """
    
    def __init__(self, puesto_repository: PuestoRepository):
        self.puesto_repository = puesto_repository
    
    def handle(self, command: ActualizarPuestoCommand) -> Dict[str, Any]:
        """
        Maneja el comando para actualizar un puesto
        """
        # Recuperar el agregado existente
        puesto_aggregate = self.puesto_repository.obtener_por_id(command.puesto_id)
        
        if not puesto_aggregate:
            raise ValueError(f"No existe una vacante con ID {command.puesto_id}")
        
        # Verificar que el puesto no esté cerrado
        if puesto_aggregate.puesto.estado == EstadoPuestoEnum.CERRADO:
            raise ValueError("No se puede actualizar una vacante cerrada")
        
        # Actualizar los campos del puesto
        puesto_aggregate.puesto.actualizar_informacion(
            titulo=command.titulo,
            descripcion=command.descripcion,
            ubicacion=command.ubicacion,
            salario_min=command.salario_min,
            salario_max=command.salario_max,
            moneda=command.moneda,
            tipo_contrato=command.tipo_contrato,
            actualizar_salario_min=command.actualizar_salario_min,
            actualizar_salario_max=command.actualizar_salario_max,
        )
        
        # Actualizar requisitos si se proporcionan
        if command.requisitos is not None:
            puesto_aggregate.actualizar_requisitos(command.requisitos)
        
        # Guardar cambios
        self.puesto_repository.guardar(puesto_aggregate)
        
        # Determinar qué campos se actualizaron
        campos_actualizados = []
        if command.titulo is not None:
            campos_actualizados.append("titulo")
        if command.descripcion is not None:
            campos_actualizados.append("descripcion")
        if command.ubicacion is not None:
            campos_actualizados.append("ubicacion")
        if command.actualizar_salario_min:
            campos_actualizados.append("salario_min")
        if command.actualizar_salario_max:
            campos_actualizados.append("salario_max")
        if command.moneda is not None:
            campos_actualizados.append("moneda")
        if command.tipo_contrato is not None:
            campos_actualizados.append("tipo_contrato")
        if command.requisitos is not None:
            campos_actualizados.append("requisitos")
        
        # Emitir evento
        puesto_aggregate.add_event(PuestoActualizado(
            puesto_id=command.puesto_id,
            campos_actualizados=campos_actualizados
        ))
        
        # Devolver el puesto actualizado
        return {
            "puesto_id": str(puesto_aggregate.puesto.puesto_id),
            "empresa_id": str(puesto_aggregate.puesto.empresa_id),
            "titulo": puesto_aggregate.puesto.titulo,
            "descripcion": puesto_aggregate.puesto.descripcion,
            "ubicacion": puesto_aggregate.puesto.ubicacion,
            "salario_min": puesto_aggregate.puesto.salario_min,
            "salario_max": puesto_aggregate.puesto.salario_max,
            "moneda": puesto_aggregate.puesto.moneda,
            "tipo_contrato": puesto_aggregate.puesto.tipo_contrato.value,
            "fecha_publicacion": puesto_aggregate.puesto.fecha_publicacion.isoformat(),
            "estado": puesto_aggregate.puesto.estado.value,
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
class CambiarEstadoPuestoCommand(Command):
    """Comando para cambiar el estado de un puesto (abierto/cerrado)"""
    puesto_id: UUID
    nuevo_estado: EstadoPuestoEnum


class CambiarEstadoPuestoHandler(CommandHandler):
    """
    Manejador del comando para cambiar el estado de un puesto
    """
    
    def __init__(self, puesto_repository: PuestoRepository):
        self.puesto_repository = puesto_repository
    
    def handle(self, command: CambiarEstadoPuestoCommand) -> Dict[str, Any]:
        """
        Maneja el comando para cambiar el estado de un puesto
        """
        # Recuperar el agregado existente
        puesto_aggregate = self.puesto_repository.obtener_por_id(command.puesto_id)
        
        if not puesto_aggregate:
            raise ValueError(f"No existe una vacante con ID {command.puesto_id}")
        
        # Aplicar el cambio de estado
        if not puesto_aggregate.cambiar_estado(command.nuevo_estado):
            raise ValueError(f"No se puede cambiar al estado {command.nuevo_estado} desde el estado actual")
        
        # Guardar cambios
        self.puesto_repository.guardar(puesto_aggregate)
        
        # Si el estado es CERRADO, emitir evento
        if command.nuevo_estado == EstadoPuestoEnum.CERRADO:
            puesto_aggregate.add_event(PuestoCerrado(
                puesto_id=command.puesto_id,
                empresa_id=puesto_aggregate.puesto.empresa_id,
                fecha_cierre=puesto_aggregate.puesto.fecha_cierre
            ))
        
        # Devolver el puesto actualizado
        return {
            "puesto_id": str(puesto_aggregate.puesto.puesto_id),
            "empresa_id": str(puesto_aggregate.puesto.empresa_id),
            "titulo": puesto_aggregate.puesto.titulo,
            "estado": puesto_aggregate.puesto.estado.value,
            "fecha_publicacion": puesto_aggregate.puesto.fecha_publicacion.isoformat(),
            "fecha_cierre": puesto_aggregate.puesto.fecha_cierre.isoformat() if puesto_aggregate.puesto.fecha_cierre else None
        }
