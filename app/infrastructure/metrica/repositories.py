from datetime import datetime
from typing import List, Optional
from uuid import NAMESPACE_URL, UUID, uuid5

from app.domain.metrica.entities import Logro, MetricaAggregate, MetricaRegistro
from app.domain.metrica.repositories import MetricaRepository
from app.domain.postulacion.entities import (
    extraer_metadatos_hito,
    normalizar_estado_postulacion,
)
from app.infrastructure.database.connection import SessionLocal
from app.infrastructure.postulacion.models import HitoModel, PostulacionModel


class MetricaRepositoryImpl(MetricaRepository):
    """Proyeccion de progreso calculada desde postulaciones e hitos reales."""

    def obtener_por_postulante(self, postulante_id: UUID) -> Optional[MetricaAggregate]:
        db = SessionLocal()
        try:
            postulaciones = (
                db.query(PostulacionModel)
                .filter(PostulacionModel.cuenta_id == str(postulante_id))
                .order_by(
                    PostulacionModel.fecha_postulacion.asc(),
                    PostulacionModel.id.asc(),
                )
                .all()
            )

            estados = {
                postulacion.id: normalizar_estado_postulacion(postulacion.estado)
                for postulacion in postulaciones
            }
            ids_postulacion = set(estados)
            hitos = (
                db.query(HitoModel)
                .filter(HitoModel.postulacion_id.in_(ids_postulacion))
                .order_by(HitoModel.fecha.asc(), HitoModel.id.asc())
                .all()
                if ids_postulacion
                else []
            )

            en_revision = {
                postulacion_id
                for postulacion_id, estado in estados.items()
                if estado == "en_revision"
            }
            entrevistas = {
                postulacion_id
                for postulacion_id, estado in estados.items()
                if estado == "entrevista"
            }
            fechas_entrevista = {}
            for hito in hitos:
                metadatos = extraer_metadatos_hito(hito.descripcion)
                estado_nuevo = normalizar_estado_postulacion(
                    hito.estado_nuevo or metadatos["estado_nuevo"] or ""
                )
                if estado_nuevo == "en_revision":
                    en_revision.add(hito.postulacion_id)
                elif estado_nuevo == "entrevista":
                    entrevistas.add(hito.postulacion_id)
                    fecha_actual = fechas_entrevista.get(hito.postulacion_id)
                    if fecha_actual is None or hito.fecha < fecha_actual:
                        fechas_entrevista[hito.postulacion_id] = hito.fecha

            # Los registros previos a los hitos estructurados siguen contando
            # su etapa actual y reciben una fecha estable para el logro.
            for postulacion in postulaciones:
                if (
                    postulacion.id in entrevistas
                    and postulacion.id not in fechas_entrevista
                ):
                    fechas_entrevista[postulacion.id] = postulacion.fecha_postulacion

            total_postulaciones = len(postulaciones)
            total_en_revision = len(en_revision)
            total_entrevistas = len(entrevistas)
            total_exitos = sum(estado == "aceptado" for estado in estados.values())
            total_rechazos = sum(estado == "rechazado" for estado in estados.values())
            tasa_exito = (
                (total_exitos / total_postulaciones) * 100
                if total_postulaciones
                else 0.0
            )

            registro = MetricaRegistro(
                cuenta_id=postulante_id,
                total_postulaciones=total_postulaciones,
                total_en_revision=total_en_revision,
                total_entrevistas=total_entrevistas,
                total_exitos=total_exitos,
                total_rechazos=total_rechazos,
                tasa_exito=tasa_exito,
            )
            return MetricaAggregate(
                metrica_registro=registro,
                lista_logros=self._calcular_logros(
                    postulante_id,
                    postulaciones,
                    min(fechas_entrevista.values()) if fechas_entrevista else None,
                ),
            )
        finally:
            db.close()

    @staticmethod
    def _calcular_logros(
        postulante_id: UUID,
        postulaciones: list,
        fecha_primera_entrevista: Optional[datetime],
    ) -> List[Logro]:
        """Proyecta logros con identificadores y fechas reproducibles."""
        logros = []

        def crear_logro(
            codigo: str,
            nombre: str,
            umbral: int,
            fecha: datetime,
        ) -> Logro:
            return Logro(
                id_logro=uuid5(
                    NAMESPACE_URL,
                    f"https://lookup.pe/logros/{postulante_id}/{codigo}",
                ),
                nombre_logro=nombre,
                umbral=umbral,
                fecha_obtencion=fecha,
            )

        if postulaciones:
            logros.append(
                crear_logro(
                    "primera-postulacion",
                    "Primera postulación",
                    1,
                    postulaciones[0].fecha_postulacion,
                )
            )

        if len(postulaciones) >= 5:
            logros.append(
                crear_logro(
                    "cinco-postulaciones",
                    "5 postulaciones enviadas",
                    5,
                    postulaciones[4].fecha_postulacion,
                )
            )

        if fecha_primera_entrevista:
            logros.append(
                crear_logro(
                    "primera-entrevista",
                    "Primera entrevista",
                    1,
                    fecha_primera_entrevista,
                )
            )

        return logros
