from dataclasses import dataclass, field
from datetime import datetime
from typing import List
from uuid import UUID, uuid4

from app.domain.common import AggregateRoot


@dataclass
class MetricaRegistro:
    """Resumen de metricas derivado del estado actual de postulaciones."""

    cuenta_id: UUID
    total_postulaciones: int = 0
    total_entrevistas: int = 0
    total_exitos: int = 0
    total_rechazos: int = 0
    tasa_exito: float = 0.0


@dataclass(frozen=True)
class Logro:
    """Logro calculado a partir de los umbrales de la proyeccion."""

    id_logro: UUID = field(default_factory=uuid4)
    nombre_logro: str = ""
    umbral: int = 0
    fecha_obtencion: datetime = field(default_factory=datetime.now)


@dataclass
class MetricaAggregate(AggregateRoot):
    metrica_registro: MetricaRegistro
    lista_logros: List[Logro] = field(default_factory=list)
