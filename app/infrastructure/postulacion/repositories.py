from typing import List, Optional
from uuid import UUID

from app.domain.postulacion.entities import (
    Postulacion,
    PostulacionAggregate,
    EstadoPostulacion,
    LineaDeTiempo,
    Hito,
    extraer_metadatos_hito,
    normalizar_estado_postulacion,
)
from app.domain.postulacion.repositories import PostulacionRepository
from app.infrastructure.database.connection import SessionLocal
from app.infrastructure.postulacion.models import PostulacionModel, HitoModel


def _hito_desde_modelo(hito_db: HitoModel) -> Hito:
    metadatos = extraer_metadatos_hito(hito_db.descripcion)
    return Hito(
        hito_id=UUID(f"00000000-0000-0000-0000-{hito_db.id:012d}"),
        fecha=hito_db.fecha,
        descripcion=hito_db.descripcion,
        tipo_evento=hito_db.tipo_evento or metadatos["tipo_evento"],
        estado_anterior=(
            normalizar_estado_postulacion(hito_db.estado_anterior)
            if hito_db.estado_anterior
            else metadatos["estado_anterior"]
        ),
        estado_nuevo=(
            normalizar_estado_postulacion(hito_db.estado_nuevo)
            if hito_db.estado_nuevo
            else metadatos["estado_nuevo"]
        ),
    )


class PostulacionRepositoryImpl(PostulacionRepository):
    """Repositorio simplificado de postulaciones"""

    def guardar(self, postulacion_aggregate: PostulacionAggregate) -> UUID:
        """Guarda o actualiza una postulación y devuelve su ID"""
        db = SessionLocal()
        try:
            post = postulacion_aggregate.postulacion
            post_id = post.postulacion_id

            # Verificar si ya existe
            post_db = (
                db.query(PostulacionModel)
                .filter(PostulacionModel.postulacion_id == str(post.postulacion_id))
                .first()
            )

            if post_db:
                # Actualizar existente
                post_db.estado = post.estado.valor.value
                post_db.cuenta_id = str(post.candidato_id)
                post_db.puesto_id = str(post.puesto_id)
                post_db.fecha_postulacion = post.fecha_postulacion
                post_db.documentos_adjuntos = list(post.documentos_adjuntos or [])

                # Eliminar hitos existentes y agregar los nuevos
                db.query(HitoModel).filter(
                    HitoModel.postulacion_id == post_db.id
                ).delete()
                db.flush()
            else:
                # Crear nueva postulación
                post_db = PostulacionModel(
                    postulacion_id=str(post.postulacion_id),
                    cuenta_id=str(post.candidato_id),
                    puesto_id=str(post.puesto_id),
                    fecha_postulacion=post.fecha_postulacion,
                    estado=post.estado.valor.value,
                    documentos_adjuntos=list(post.documentos_adjuntos or []),
                    resultado=None,
                )
                db.add(post_db)
                db.flush()

            # Guardar todos los hitos
            for hito in postulacion_aggregate.linea_de_tiempo.lista_hitos:
                hito_db = HitoModel(
                    postulacion_id=post_db.id,
                    fecha=hito.fecha,
                    descripcion=hito.descripcion,
                    tipo_evento=hito.tipo_evento,
                    estado_anterior=hito.estado_anterior,
                    estado_nuevo=hito.estado_nuevo,
                )
                db.add(hito_db)

            db.commit()
            return post_id

        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    def obtener_por_id(self, postulacion_id: UUID) -> Optional[PostulacionAggregate]:
        """Obtiene una postulación por ID"""
        db = SessionLocal()
        try:
            # Buscar por postulacion_id (UUID)
            post_db = (
                db.query(PostulacionModel)
                .filter(PostulacionModel.postulacion_id == str(postulacion_id))
                .first()
            )

            if not post_db:
                return None

            post = Postulacion(
                postulacion_id=UUID(post_db.postulacion_id)
                if post_db.postulacion_id
                else postulacion_id,
                candidato_id=UUID(post_db.cuenta_id),
                puesto_id=UUID(post_db.puesto_id)
                if post_db.puesto_id
                else UUID("00000000-0000-0000-0000-000000000001"),
                fecha_postulacion=post_db.fecha_postulacion,
                estado=EstadoPostulacion(post_db.estado),
                documentos_adjuntos=list(post_db.documentos_adjuntos or []),
            )

            linea_tiempo = LineaDeTiempo()
            for hito_db in post_db.hitos:
                linea_tiempo.lista_hitos.append(_hito_desde_modelo(hito_db))

            return PostulacionAggregate(
                postulacion=post, estado=post.estado, linea_de_tiempo=linea_tiempo
            )
        finally:
            db.close()

    def obtener_por_candidato(self, candidato_id: UUID) -> List[PostulacionAggregate]:
        """Obtiene todas las postulaciones de un candidato"""
        db = SessionLocal()
        try:
            posts_db = (
                db.query(PostulacionModel)
                .filter(PostulacionModel.cuenta_id == str(candidato_id))
                .all()
            )

            resultado = []
            for post_db in posts_db:
                post = Postulacion(
                    postulacion_id=UUID(post_db.postulacion_id)
                    if post_db.postulacion_id
                    else UUID("00000000-0000-0000-0000-000000000001"),
                    candidato_id=UUID(post_db.cuenta_id),
                    puesto_id=UUID(post_db.puesto_id)
                    if post_db.puesto_id
                    else UUID("00000000-0000-0000-0000-000000000001"),
                    fecha_postulacion=post_db.fecha_postulacion,
                    estado=EstadoPostulacion(post_db.estado),
                    documentos_adjuntos=list(post_db.documentos_adjuntos or []),
                )

                linea_tiempo = LineaDeTiempo()
                for hito_db in post_db.hitos:
                    linea_tiempo.lista_hitos.append(_hito_desde_modelo(hito_db))

                resultado.append(
                    PostulacionAggregate(
                        postulacion=post,
                        estado=post.estado,
                        linea_de_tiempo=linea_tiempo,
                    )
                )

            return resultado
        finally:
            db.close()

    def obtener_por_puesto(self, puesto_id: UUID) -> List[PostulacionAggregate]:
        """Obtiene todas las postulaciones para un puesto"""
        db = SessionLocal()
        try:
            posts_db = (
                db.query(PostulacionModel)
                .filter(PostulacionModel.puesto_id == str(puesto_id))
                .all()
            )

            resultado = []
            for post_db in posts_db:
                post = Postulacion(
                    postulacion_id=UUID(post_db.postulacion_id)
                    if post_db.postulacion_id
                    else UUID("00000000-0000-0000-0000-000000000001"),
                    candidato_id=UUID(post_db.cuenta_id),
                    puesto_id=UUID(post_db.puesto_id)
                    if post_db.puesto_id
                    else UUID("00000000-0000-0000-0000-000000000001"),
                    fecha_postulacion=post_db.fecha_postulacion,
                    estado=EstadoPostulacion(post_db.estado),
                    documentos_adjuntos=list(post_db.documentos_adjuntos or []),
                )

                linea_tiempo = LineaDeTiempo()
                for hito_db in post_db.hitos:
                    linea_tiempo.lista_hitos.append(_hito_desde_modelo(hito_db))

                resultado.append(
                    PostulacionAggregate(
                        postulacion=post,
                        estado=post.estado,
                        linea_de_tiempo=linea_tiempo,
                    )
                )

            return resultado
        finally:
            db.close()
