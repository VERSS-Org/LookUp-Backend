from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from app.domain.metrica.entities import MetricaAggregate


class MetricaRepository(ABC):
    """Consulta la proyeccion de metricas derivada de postulaciones."""

    @abstractmethod
    def obtener_por_postulante(
        self, postulante_id: UUID
    ) -> Optional[MetricaAggregate]:
        pass
