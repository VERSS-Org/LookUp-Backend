from dataclasses import dataclass
from typing import Any, Dict
from uuid import UUID

from app.domain.common import Command, CommandHandler
from app.domain.metrica.repositories import MetricaRepository


@dataclass
class RecalcularMetricasCommand(Command):
    cuenta_id: UUID


class RecalcularMetricasHandler(CommandHandler):
    """Vuelve a leer la proyeccion calculada en tiempo real."""

    def __init__(self, metrica_repository: MetricaRepository):
        self.metrica_repository = metrica_repository

    def handle(self, command: RecalcularMetricasCommand) -> Dict[str, Any]:
        metrica = self.metrica_repository.obtener_por_postulante(
            command.cuenta_id
        )
        if not metrica:
            return {
                "cuenta_id": str(command.cuenta_id),
                "total_postulaciones": 0,
                "total_entrevistas": 0,
                "total_exitos": 0,
                "total_rechazos": 0,
                "tasa_exito": 0.0,
            }

        registro = metrica.metrica_registro
        return {
            "cuenta_id": str(registro.cuenta_id),
            "total_postulaciones": registro.total_postulaciones,
            "total_entrevistas": registro.total_entrevistas,
            "total_exitos": registro.total_exitos,
            "total_rechazos": registro.total_rechazos,
            "tasa_exito": registro.tasa_exito,
        }
