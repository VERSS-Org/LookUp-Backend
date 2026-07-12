from collections import Counter
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func

from app.domain.metrica.entities import Logro, MetricaAggregate, MetricaRegistro
from app.domain.metrica.repositories import MetricaRepository
from app.domain.postulacion.entities import normalizar_estado_postulacion
from app.infrastructure.database.connection import SessionLocal
from app.infrastructure.postulacion.models import PostulacionModel


class MetricaRepositoryImpl(MetricaRepository):
    """Proyeccion de metricas calculada desde las postulaciones actuales."""

    def obtener_por_postulante(
        self, postulante_id: UUID
    ) -> Optional[MetricaAggregate]:
        db = SessionLocal()
        try:
            # SQLAlchemy persiste los nombres del Enum (p. ej. ENTREVISTA), no
            # sus valores en minuscula. Agrupar por Enum y normalizar despues
            # evita contadores en cero y conserva lectura de estados antiguos.
            filas = (
                db.query(
                    PostulacionModel.estado,
                    func.count(PostulacionModel.id),
                )
                .filter(PostulacionModel.cuenta_id == str(postulante_id))
                .group_by(PostulacionModel.estado)
                .all()
            )

            conteos = Counter()
            for estado, total in filas:
                conteos[normalizar_estado_postulacion(estado)] += int(total)

            total_postulaciones = sum(conteos.values())
            total_entrevistas = conteos["entrevista"]
            total_exitos = conteos["aceptado"]
            total_rechazos = conteos["rechazado"]
            tasa_exito = (
                (total_exitos / total_postulaciones) * 100
                if total_postulaciones
                else 0.0
            )

            registro = MetricaRegistro(
                cuenta_id=postulante_id,
                total_postulaciones=total_postulaciones,
                total_entrevistas=total_entrevistas,
                total_exitos=total_exitos,
                total_rechazos=total_rechazos,
                tasa_exito=tasa_exito,
            )
            return MetricaAggregate(
                metrica_registro=registro,
                lista_logros=self._calcular_logros(
                    total_postulaciones,
                    total_entrevistas,
                    total_exitos,
                ),
            )
        finally:
            db.close()

    @staticmethod
    def _calcular_logros(
        total_postulaciones: int,
        total_entrevistas: int,
        total_exitos: int,
    ) -> List[Logro]:
        logros = []

        if total_postulaciones >= 10:
            logros.append(
                Logro(
                    nombre_logro="Postulante Activo",
                    umbral=10,
                    fecha_obtencion=datetime.now(),
                )
            )

        if total_entrevistas >= 5:
            logros.append(
                Logro(
                    nombre_logro="Entrevistado Frecuente",
                    umbral=5,
                    fecha_obtencion=datetime.now(),
                )
            )

        if total_exitos >= 1:
            logros.append(
                Logro(
                    nombre_logro="Primera Aceptación",
                    umbral=1,
                    fecha_obtencion=datetime.now(),
                )
            )

        if total_exitos >= 3:
            logros.append(
                Logro(
                    nombre_logro="Postulante Destacado",
                    umbral=3,
                    fecha_obtencion=datetime.now(),
                )
            )

        return logros
