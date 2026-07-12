from fastapi import APIRouter, Depends, HTTPException, status, Path, Query
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from app.application.postulacion.command_handlers import (
    PostularHandler, PostularCommand,
    ActualizarEstadoPostulacionHandler, ActualizarEstadoCommand
)
from app.application.postulacion.postulacion_service import PostulacionService
from app.domain.postulacion.entities import (
    extraer_metadatos_hito,
    normalizar_estado_postulacion,
)
from app.infrastructure.contacto.models import ContactoPostulacionModel, FeedbackModel
from app.infrastructure.database.connection import SessionLocal
from app.infrastructure.iam.models import CuentaModel
from app.infrastructure.postulacion.models import HitoModel, PostulacionModel
from app.infrastructure.postulacion.repositories import PostulacionRepositoryImpl
from app.infrastructure.puesto.models import PuestoMapeo, PuestoModel
from app.infrastructure.puesto.repositories import PuestoRepositoryImpl
from app.interface.api.dependencies import obtener_usuario_actual

from .schemas import (
    PostulacionCreate, PostulacionEnriquecidaResponse,
    EstadoUpdate, EstadoPostulacionEnum, EventoRecienteResponse
)

router = APIRouter(prefix="/postulacion", tags=["Postulación"])
postulacion_service = PostulacionService()


def _require_role(usuario: dict, rol: str) -> None:
    if usuario.get("rol") != rol:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Operación permitida solo para el rol {rol}"
        )


def _require_same_account(cuenta_id: UUID, usuario: dict) -> None:
    if str(cuenta_id) != str(usuario.get("cuenta_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No puedes operar con una cuenta distinta a la autenticada"
        )


def _serialize_postulacion(aggregate) -> dict:
    estado = normalizar_estado_postulacion(aggregate.postulacion.estado.valor)

    return {
        "postulacion_id": str(aggregate.postulacion.postulacion_id),
        "candidato_id": str(aggregate.postulacion.candidato_id),
        "puesto_id": str(aggregate.postulacion.puesto_id),
        "fecha_postulacion": aggregate.postulacion.fecha_postulacion.isoformat(),
        "estado": estado,
        "documentos_adjuntos": aggregate.postulacion.documentos_adjuntos,
        "hitos": [
            {
                "hito_id": str(hito.hito_id),
                "fecha": hito.fecha.isoformat(),
                "descripcion": hito.descripcion,
                "tipo_evento": hito.tipo_evento,
                "estado_anterior": hito.estado_anterior,
                "estado_nuevo": hito.estado_nuevo,
            }
            for hito in aggregate.linea_de_tiempo.lista_hitos
        ]
    }


def _obtener_puesto_o_404(puesto_id: UUID):
    puesto = PuestoRepositoryImpl().obtener_por_id(puesto_id)
    if not puesto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vacante con ID {puesto_id} no encontrada"
        )
    return puesto


def _require_empresa_owner(puesto_id: UUID, usuario: dict) -> None:
    _require_role(usuario, "empresa")
    puesto = _obtener_puesto_o_404(puesto_id)
    if str(puesto.puesto.empresa_id) != str(usuario.get("cuenta_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No puedes gestionar postulaciones de una vacante de otra empresa"
        )


def _require_postulacion_access(aggregate, usuario: dict) -> None:
    if usuario.get("rol") == "postulante":
        _require_same_account(aggregate.postulacion.candidato_id, usuario)
        return

    if usuario.get("rol") == "empresa":
        _require_empresa_owner(aggregate.postulacion.puesto_id, usuario)
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Rol no autorizado para consultar postulaciones"
    )


@router.post("/", response_model=PostulacionEnriquecidaResponse, status_code=status.HTTP_201_CREATED)
async def crear_postulacion(
    postulacion: PostulacionCreate,
    usuario: dict = Depends(obtener_usuario_actual)
):
    """
    Crea una nueva postulación para el postulante autenticado.
    """
    try:
        _require_role(usuario, "postulante")
        candidato_id = UUID(postulacion.candidato_id)
        _require_same_account(candidato_id, usuario)

        postulacion_repository = PostulacionRepositoryImpl()
        puesto_repository = PuestoRepositoryImpl()
        handler = PostularHandler(postulacion_repository, puesto_repository)
        command = PostularCommand(
            candidato_id=candidato_id,
            puesto_id=UUID(postulacion.puesto_id),
            documentos_adjuntos=postulacion.documentos_adjuntos or []
        )
        resultado = handler.handle(command)

        aggregate = postulacion_repository.obtener_por_id(resultado)
        if aggregate is None:
            raise RuntimeError("No se pudo recuperar la postulación creada")
        return postulacion_service.enriquecer_postulacion(
            _serialize_postulacion(aggregate)
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


ESTADOS_RETIRABLES = {"pendiente", "en_revision", "entrevista"}


@router.get("/eventos", response_model=List[EventoRecienteResponse])
async def eventos_recientes(usuario: dict = Depends(obtener_usuario_actual)):
    """
    Novedades de los últimos 7 días para el usuario autenticado:
    - postulante: hitos de sus postulaciones (cambios de estado, etc.).
    - empresa: nuevas postulaciones recibidas en sus vacantes.
    """
    from datetime import timedelta

    rol = usuario.get("rol")
    cuenta_id = str(usuario["cuenta_id"])
    corte = datetime.now() - timedelta(days=7)

    db = SessionLocal()
    try:
        eventos = []
        if rol == "postulante":
            postulaciones = db.query(PostulacionModel).filter(
                PostulacionModel.cuenta_id == cuenta_id
            ).all()
            if not postulaciones:
                return []
            por_pk = {p.id: p for p in postulaciones}
            hitos = db.query(HitoModel).filter(
                HitoModel.postulacion_id.in_(por_pk.keys()),
                HitoModel.fecha >= corte,
            ).order_by(HitoModel.fecha.desc()).limit(30).all()

            titulos = _titulos_de_puestos(
                db, {p.puesto_id for p in postulaciones}
            )
            for hito in hitos:
                postulacion = por_pk.get(hito.postulacion_id)
                if not postulacion:
                    continue
                metadatos = extraer_metadatos_hito(hito.descripcion)
                eventos.append({
                    "tipo": "hito",
                    "tipo_evento": (
                        hito.tipo_evento or metadatos["tipo_evento"]
                    ),
                    "titulo": titulos.get(postulacion.puesto_id),
                    "descripcion": hito.descripcion,
                    "fecha": hito.fecha.isoformat(),
                    "postulacion_id": postulacion.postulacion_id,
                    "estado_anterior": (
                        normalizar_estado_postulacion(hito.estado_anterior)
                        if hito.estado_anterior
                        else metadatos["estado_anterior"]
                    ),
                    "estado_nuevo": (
                        normalizar_estado_postulacion(hito.estado_nuevo)
                        if hito.estado_nuevo
                        else metadatos["estado_nuevo"]
                    ),
                })
        elif rol == "empresa":
            bd_ids = [
                fila.id for fila in db.query(PuestoModel.id).filter(
                    PuestoModel.empresa == cuenta_id
                ).all()
            ]
            if not bd_ids:
                return []
            uuids = {
                m.uuid_id: m.bd_id
                for m in db.query(PuestoMapeo).filter(
                    PuestoMapeo.bd_id.in_(bd_ids)
                ).all()
            }
            if not uuids:
                return []
            postulaciones = db.query(PostulacionModel).filter(
                PostulacionModel.puesto_id.in_(uuids.keys()),
                PostulacionModel.fecha_postulacion >= corte,
            ).order_by(PostulacionModel.fecha_postulacion.desc()).limit(30).all()

            titulos = _titulos_de_puestos(
                db, {p.puesto_id for p in postulaciones}
            )
            candidatos = {
                str(c.id): c.nombre_completo
                for c in db.query(CuentaModel).filter(
                    CuentaModel.id.in_({p.cuenta_id for p in postulaciones})
                ).all()
            } if postulaciones else {}
            for postulacion in postulaciones:
                nombre = candidatos.get(postulacion.cuenta_id, "Un postulante")
                eventos.append({
                    "tipo": "postulacion",
                    "tipo_evento": "postulacion_recibida",
                    "titulo": titulos.get(postulacion.puesto_id),
                    "descripcion": nombre,
                    "fecha": postulacion.fecha_postulacion.isoformat(),
                    "postulacion_id": postulacion.postulacion_id,
                    "estado_nuevo": "pendiente",
                })
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Rol no autorizado"
            )

        eventos.sort(key=lambda e: e["fecha"], reverse=True)
        return eventos
    finally:
        db.close()


def _titulos_de_puestos(db, puesto_uuids: set) -> dict:
    """Mapa uuid del puesto -> título, resolviendo el mapeo UUID/PK."""
    if not puesto_uuids:
        return {}
    mapeos = {
        m.uuid_id: m.bd_id
        for m in db.query(PuestoMapeo).filter(
            PuestoMapeo.uuid_id.in_(puesto_uuids)
        ).all()
    }
    if not mapeos:
        return {}
    puestos = {
        p.id: p.titulo
        for p in db.query(PuestoModel).filter(
            PuestoModel.id.in_(set(mapeos.values()))
        ).all()
    }
    return {
        uuid_id: puestos.get(bd_id)
        for uuid_id, bd_id in mapeos.items()
    }


@router.delete("/{postulacion_id}", status_code=status.HTTP_200_OK)
async def retirar_postulacion(
    postulacion_id: str = Path(..., title="ID de la postulación"),
    usuario: dict = Depends(obtener_usuario_actual)
):
    """
    Retira (elimina) una postulación del postulante autenticado.
    Solo es posible mientras el proceso sigue activo (pendiente, en revisión
    o entrevista); una vez aceptado o rechazado ya no se puede retirar.
    """
    try:
        _require_role(usuario, "postulante")
        postulacion_repository = PostulacionRepositoryImpl()
        aggregate = postulacion_repository.obtener_por_id(UUID(postulacion_id))
        if aggregate is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Postulación con ID {postulacion_id} no encontrada"
            )
        _require_same_account(aggregate.postulacion.candidato_id, usuario)

        estado = normalizar_estado_postulacion(
            aggregate.postulacion.estado.valor
        )
        if estado not in ESTADOS_RETIRABLES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La postulación ya no se puede retirar en su estado actual"
            )

        db = SessionLocal()
        try:
            contacto_ids = [
                c.id for c in db.query(ContactoPostulacionModel.id).filter(
                    ContactoPostulacionModel.postulacion_id == postulacion_id
                ).all()
            ]
            if contacto_ids:
                db.query(FeedbackModel).filter(
                    FeedbackModel.contacto_id.in_(contacto_ids)
                ).delete(synchronize_session=False)
                db.query(ContactoPostulacionModel).filter(
                    ContactoPostulacionModel.id.in_(contacto_ids)
                ).delete(synchronize_session=False)

            fila = db.query(PostulacionModel).filter(
                PostulacionModel.postulacion_id == postulacion_id
            ).first()
            if fila:
                db.query(HitoModel).filter(
                    HitoModel.postulacion_id == fila.id
                ).delete(synchronize_session=False)
                db.delete(fila)
            db.commit()
        finally:
            db.close()

        return {"mensaje": "Postulación retirada", "postulacion_id": postulacion_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{postulacion_id}", response_model=PostulacionEnriquecidaResponse)
async def obtener_postulacion(
    postulacion_id: str = Path(..., title="ID de la postulación"),
    usuario: dict = Depends(obtener_usuario_actual)
):
    """
    Obtiene una postulación con datos enriquecidos si pertenece al usuario autenticado.
    """
    try:
        postulacion_repository = PostulacionRepositoryImpl()
        aggregate = postulacion_repository.obtener_por_id(UUID(postulacion_id))
        if aggregate is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Postulación con ID {postulacion_id} no encontrada"
            )

        _require_postulacion_access(aggregate, usuario)
        return postulacion_service.enriquecer_postulacion(_serialize_postulacion(aggregate))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Postulación con ID {postulacion_id} no encontrada"
        )


@router.get("/", response_model=List[PostulacionEnriquecidaResponse])
async def listar_postulaciones(
    candidato_id: Optional[str] = Query(None, title="ID del postulante"),
    puesto_id: Optional[str] = Query(None, title="ID de la vacante"),
    estado: Optional[EstadoPostulacionEnum] = Query(None, title="Estado de la postulación"),
    enriquecer: bool = Query(True, title="Incluir datos enriquecidos"),
    usuario: dict = Depends(obtener_usuario_actual)
):
    """
    Lista postulaciones por postulante o por vacante respetando la cuenta autenticada.
    """
    try:
        postulacion_repository = PostulacionRepositoryImpl()

        if puesto_id:
            puesto_uuid = UUID(puesto_id)
            _require_empresa_owner(puesto_uuid, usuario)
            resultados = postulacion_repository.obtener_por_puesto(puesto_uuid)
        elif candidato_id:
            candidato_uuid = UUID(candidato_id)
            _require_role(usuario, "postulante")
            _require_same_account(candidato_uuid, usuario)
            resultados = postulacion_repository.obtener_por_candidato(candidato_uuid)
        else:
            return []

        if estado:
            estado_filtro = normalizar_estado_postulacion(estado.value)
            resultados = [
                aggregate for aggregate in resultados
                if normalizar_estado_postulacion(
                    aggregate.postulacion.estado.valor
                ) == estado_filtro
            ]

        respuestas = [_serialize_postulacion(aggregate) for aggregate in resultados]
        if enriquecer:
            return postulacion_service.enriquecer_postulaciones(respuestas)
        return respuestas
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.patch("/{postulacion_id}/estado", response_model=PostulacionEnriquecidaResponse)
async def actualizar_estado_postulacion(
    estado_update: EstadoUpdate,
    postulacion_id: str = Path(..., title="ID de la postulación"),
    usuario: dict = Depends(obtener_usuario_actual)
):
    """
    Actualiza el estado de una postulación solo si la empresa es dueña de la vacante.
    """
    try:
        postulacion_repository = PostulacionRepositoryImpl()
        postulacion_actual = postulacion_repository.obtener_por_id(UUID(postulacion_id))
        if not postulacion_actual:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Postulación con ID {postulacion_id} no encontrada"
            )

        _require_empresa_owner(postulacion_actual.postulacion.puesto_id, usuario)

        handler = ActualizarEstadoPostulacionHandler(postulacion_repository)
        command = ActualizarEstadoCommand(
            postulacion_id=UUID(postulacion_id),
            nuevo_estado=estado_update.nuevo_estado
        )
        resultado = handler.handle(command)

        if not resultado:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se pudo actualizar el estado de la postulación"
            )

        postulacion_actualizada = postulacion_repository.obtener_por_id(UUID(postulacion_id))
        if not postulacion_actualizada:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Postulación con ID {postulacion_id} no encontrada"
            )

        return postulacion_service.enriquecer_postulacion(
            _serialize_postulacion(postulacion_actualizada)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
