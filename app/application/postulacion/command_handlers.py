from dataclasses import dataclass, field
from typing import Any, Dict, List
from uuid import UUID

from app.domain.common import Command, CommandHandler
from app.domain.postulacion.entities import (
    EstadoPostulacion,
    EstadoPostulacionEnum,
    LineaDeTiempo,
    Postulacion,
    PostulacionAggregate,
)
from app.domain.postulacion.repositories import PostulacionRepository
from app.domain.puesto.entities import EstadoPuestoEnum
from app.domain.puesto.repositories import PuestoRepository


@dataclass
class PostularCommand(Command):
    candidato_id: UUID
    puesto_id: UUID
    documentos_adjuntos: List[Dict[str, Any]] = field(default_factory=list)


class PostularHandler(CommandHandler):
    def __init__(
        self,
        postulacion_repository: PostulacionRepository,
        puesto_repository: PuestoRepository,
    ):
        self.postulacion_repository = postulacion_repository
        self.puesto_repository = puesto_repository

    def handle(self, command: PostularCommand) -> UUID:
        puesto = self.puesto_repository.obtener_por_id(command.puesto_id)
        estado_puesto = (
            puesto.puesto.estado.value
            if puesto and hasattr(puesto.puesto.estado, "value")
            else puesto.puesto.estado if puesto else None
        )
        if not puesto or estado_puesto != EstadoPuestoEnum.ABIERTO.value:
            raise ValueError("La vacante no existe o ya no esta disponible")

        postulaciones_existentes = self.postulacion_repository.obtener_por_candidato(
            command.candidato_id
        )
        if any(
            postulacion.postulacion.puesto_id == command.puesto_id
            for postulacion in postulaciones_existentes
        ):
            raise ValueError("Ya existe una postulacion para esta vacante")

        postulacion = Postulacion(
            candidato_id=command.candidato_id,
            puesto_id=command.puesto_id,
            documentos_adjuntos=list(command.documentos_adjuntos),
        )
        estado = EstadoPostulacion(EstadoPostulacionEnum.PENDIENTE)
        aggregate = PostulacionAggregate(
            postulacion=postulacion,
            estado=estado,
            linea_de_tiempo=LineaDeTiempo(),
        )
        aggregate.postularse()
        return self.postulacion_repository.guardar(aggregate)


@dataclass
class ActualizarEstadoCommand(Command):
    postulacion_id: UUID
    nuevo_estado: str


class ActualizarEstadoPostulacionHandler(CommandHandler):
    def __init__(self, postulacion_repository: PostulacionRepository):
        self.postulacion_repository = postulacion_repository

    def handle(self, command: ActualizarEstadoCommand) -> bool:
        aggregate = self.postulacion_repository.obtener_por_id(
            command.postulacion_id
        )
        if not aggregate:
            raise ValueError(
                f"No existe una postulacion con ID {command.postulacion_id}"
            )
        if not aggregate.cambiar_estado(command.nuevo_estado):
            return False
        self.postulacion_repository.guardar(aggregate)
        return True
