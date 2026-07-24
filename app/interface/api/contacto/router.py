from fastapi import APIRouter, Depends, HTTPException, status, Path, Query
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from app.application.contacto.command_handlers import (
    EnviarFeedbackCommandHandler, EnviarFeedbackCommand
)
from app.application.postulacion.command_handlers import (
    ActualizarEstadoCommand, ActualizarEstadoPostulacionHandler
)
from app.application.contacto.query_handlers import (
    ObtenerContactoQueryHandler, ObtenerContactoQuery,
    ObtenerContactosPostulacionQueryHandler, ObtenerContactosPostulacionQuery
)
from app.domain.contacto.entities import (
    ContactoAggregate, ContactoPostulacion, Feedback,
    TipoFeedbackEnum as DomainTipoFeedbackEnum,
    TipoMensajeEnum as DomainTipoMensajeEnum
)
from app.domain.postulacion.entities import normalizar_estado_postulacion
from app.infrastructure.contacto.models import ContactoPostulacionModel, FeedbackModel
from app.infrastructure.contacto.repositories import ContactoRepositoryImpl
from app.infrastructure.database.connection import SessionLocal
from app.infrastructure.iam.models import CuentaModel
from app.infrastructure.postulacion.models import PostulacionModel
from app.infrastructure.postulacion.repositories import PostulacionRepositoryImpl
from app.infrastructure.puesto.models import PuestoModel, PuestoMapeo
from app.infrastructure.puesto.repositories import PuestoRepositoryImpl
from app.interface.api.dependencies import obtener_usuario_actual

from .schemas import (
    ContactoResponse,
    FeedbackCreate, FeedbackResponse, MensajeContactoCreate, TipoContactoEnum
)

router = APIRouter(prefix="/contacto", tags=["Mensajería"])


def _require_role(usuario: dict, rol: str) -> None:
    if usuario.get("rol") != rol:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Operación permitida solo para el rol {rol}"
        )


def _obtener_postulacion_o_404(postulacion_id: UUID):
    postulacion = PostulacionRepositoryImpl().obtener_por_id(postulacion_id)
    if not postulacion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Postulación con ID {postulacion_id} no encontrada"
        )
    return postulacion


def _require_empresa_owner(postulacion, usuario: dict) -> None:
    _require_role(usuario, "empresa")
    puesto = PuestoRepositoryImpl().obtener_por_id(postulacion.postulacion.puesto_id)
    if not puesto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vacante asociada a la postulación no encontrada"
        )
    if str(puesto.puesto.empresa_id) != str(usuario.get("cuenta_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No puedes gestionar feedback de una vacante de otra empresa"
        )


def _require_postulacion_access(postulacion, usuario: dict) -> None:
    if usuario.get("rol") == "postulante":
        if str(postulacion.postulacion.candidato_id) != str(usuario.get("cuenta_id")):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No puedes consultar mensajes de otra cuenta"
            )
        return

    if usuario.get("rol") == "empresa":
        _require_empresa_owner(postulacion, usuario)
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Rol no autorizado para consultar mensajes"
    )


def _estado_desde_feedback(tipo_feedback: str) -> Optional[str]:
    if tipo_feedback == "aprobacion":
        return "aceptado"
    if tipo_feedback == "rechazo":
        return "rechazado"
    return None


@router.get("/bandeja")
async def bandeja_de_mensajes(usuario: dict = Depends(obtener_usuario_actual)):
    """
    Bandeja de conversaciones del usuario autenticado (postulante o empresa):
    una entrada por postulación con mensajes, el último mensaje, el número de
    no leidos y los datos de la contraparte (nombre y foto).
    """
    rol = usuario.get("rol")
    if rol not in ("postulante", "empresa"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Rol no autorizado para la bandeja de mensajes"
        )

    cuenta_id = str(usuario["cuenta_id"])
    db = SessionLocal()
    try:
        query = db.query(ContactoPostulacionModel)
        if rol == "empresa":
            query = query.filter(ContactoPostulacionModel.empresa_id == cuenta_id)
        else:
            query = query.filter(ContactoPostulacionModel.cuenta_id == cuenta_id)
        contactos = query.order_by(ContactoPostulacionModel.fecha_hora.asc()).all()

        # Agrupar por postulacion conservando el ultimo mensaje y los no leidos.
        hilos: dict = {}
        for contacto in contactos:
            hilo = hilos.setdefault(contacto.postulacion_id, {
                "postulacion_id": contacto.postulacion_id,
                "total_mensajes": 0,
                "no_leidos": 0,
                "_ultimo": None,
            })
            hilo["total_mensajes"] += 1
            if contacto.remitente_rol != rol and not bool(contacto.leido):
                hilo["no_leidos"] += 1
            hilo["_ultimo"] = contacto

        if not hilos:
            return []

        postulacion_ids = list(hilos.keys())
        postulaciones = {
            p.postulacion_id: p
            for p in db.query(PostulacionModel)
            .filter(PostulacionModel.postulacion_id.in_(postulacion_ids)).all()
        }
        # Los puestos usan PK entera con mapeo UUID -> id en puesto_mapeo.
        puesto_uuids = {p.puesto_id for p in postulaciones.values()}
        mapeos = {
            m.uuid_id: m.bd_id
            for m in db.query(PuestoMapeo)
            .filter(PuestoMapeo.uuid_id.in_(puesto_uuids)).all()
        }
        puestos_por_bd_id = {
            p.id: p
            for p in db.query(PuestoModel)
            .filter(PuestoModel.id.in_(set(mapeos.values()))).all()
        } if mapeos else {}
        puestos = {
            uuid_id: puestos_por_bd_id.get(bd_id)
            for uuid_id, bd_id in mapeos.items()
        }
        contraparte_ids = set()
        for postulacion_id, hilo in hilos.items():
            ultimo = hilo["_ultimo"]
            contraparte_ids.add(
                ultimo.cuenta_id if rol == "empresa" else ultimo.empresa_id
            )
        contraparte_uuids = set()
        for contraparte_id in contraparte_ids:
            try:
                contraparte_uuids.add(UUID(str(contraparte_id)))
            except (TypeError, ValueError):
                continue
        cuentas = {
            str(c.id): c
            for c in db.query(CuentaModel)
            .filter(CuentaModel.id.in_(contraparte_uuids)).all()
        } if contraparte_uuids else {}

        resultado = []
        for postulacion_id, hilo in hilos.items():
            ultimo = hilo.pop("_ultimo")
            feedback = db.query(FeedbackModel).filter(
                FeedbackModel.contacto_id == ultimo.id
            ).first()
            postulacion = postulaciones.get(postulacion_id)
            puesto = puestos.get(postulacion.puesto_id) if postulacion else None
            contraparte_id = (
                ultimo.cuenta_id if rol == "empresa" else ultimo.empresa_id
            )
            contraparte = cuentas.get(str(contraparte_id))

            estado = postulacion.estado.value if postulacion and hasattr(
                postulacion.estado, "value") else (
                postulacion.estado if postulacion else None)
            if estado is not None:
                estado = normalizar_estado_postulacion(estado)

            resultado.append({
                **hilo,
                "estado_postulacion": estado,
                "puesto_id": postulacion.puesto_id if postulacion else None,
                "puesto_titulo": puesto.titulo if puesto else None,
                "contraparte": {
                    "cuenta_id": str(contraparte_id),
                    "nombre": contraparte.nombre_completo if contraparte else None,
                    "foto_url": contraparte.foto_url if contraparte else None,
                },
                "ultimo_mensaje": {
                    "texto": feedback.mensaje_texto if feedback else None,
                    "tipo": feedback.tipo.value if feedback and hasattr(
                        feedback.tipo, "value") else (
                        feedback.tipo if feedback else None),
                    "remitente_rol": ultimo.remitente_rol,
                    "fecha": ultimo.fecha_hora.isoformat(),
                },
            })

        resultado.sort(
            key=lambda h: h["ultimo_mensaje"]["fecha"] or "", reverse=True
        )
        return resultado
    finally:
        db.close()


@router.post("/marcar-leidos")
async def marcar_leidos(
    mensaje: dict,
    usuario: dict = Depends(obtener_usuario_actual)
):
    """
    Marca como leídos todos los mensajes de una postulación enviados por la
    contraparte. Body: {"postulacion_id": "..."}.
    """
    postulacion_id = str(mensaje.get("postulacion_id") or "")
    if not postulacion_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="postulacion_id es requerido"
        )

    postulacion = _obtener_postulacion_o_404(UUID(postulacion_id))
    _require_postulacion_access(postulacion, usuario)

    db = SessionLocal()
    try:
        actualizados = db.query(ContactoPostulacionModel).filter(
            ContactoPostulacionModel.postulacion_id == postulacion_id,
            ContactoPostulacionModel.remitente_rol != usuario["rol"],
            ContactoPostulacionModel.leido.is_(False),
        ).update({ContactoPostulacionModel.leido: True},
                 synchronize_session=False)
        db.commit()
        return {"actualizados": actualizados}
    finally:
        db.close()


@router.post("/mensaje", response_model=ContactoResponse, status_code=status.HTTP_201_CREATED)
async def enviar_mensaje_contacto(
    mensaje: MensajeContactoCreate,
    usuario: dict = Depends(obtener_usuario_actual)
):
    try:
        postulacion = _obtener_postulacion_o_404(UUID(mensaje.postulacion_id))
        _require_postulacion_access(postulacion, usuario)

        texto = mensaje.mensaje_texto.strip()
        if not texto:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="mensaje_texto no puede estar vacío"
            )

        puesto = PuestoRepositoryImpl().obtener_por_id(postulacion.postulacion.puesto_id)
        if not puesto:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vacante asociada a la postulación no encontrada"
            )

        contacto = ContactoPostulacion(
            postulacion_id=postulacion.postulacion.postulacion_id,
            empresa_id=puesto.puesto.empresa_id,
            cuenta_id=postulacion.postulacion.candidato_id,
            tipo_mensaje=DomainTipoMensajeEnum.ACTUALIZACION,
            remitente_rol=usuario["rol"]
        )
        feedback = Feedback(
            tipo=DomainTipoFeedbackEnum.OTRO,
            mensaje_texto=texto
        )
        contacto_aggregate = ContactoAggregate(contacto_postulacion=contacto)
        contacto_aggregate.procesar_feedback(feedback)

        contacto_repository = ContactoRepositoryImpl()
        contacto_id = contacto_repository.guardar(contacto_aggregate)
        resultado = ObtenerContactoQueryHandler(contacto_repository).handle(
            ObtenerContactoQuery(contacto_id=contacto_id)
        )
        return ContactoResponse(**resultado)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{contacto_id}", response_model=ContactoResponse)
async def obtener_contacto(
    contacto_id: str = Path(..., title="ID del contacto"),
    usuario: dict = Depends(obtener_usuario_actual)
):
    try:
        contacto_repository = ContactoRepositoryImpl()
        contacto = contacto_repository.obtener_por_id(UUID(contacto_id))
        if not contacto:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Contacto con ID {contacto_id} no encontrado"
            )

        postulacion = _obtener_postulacion_o_404(contacto.contacto_postulacion.postulacion_id)
        _require_postulacion_access(postulacion, usuario)

        handler = ObtenerContactoQueryHandler(contacto_repository)
        resultado = handler.handle(ObtenerContactoQuery(contacto_id=UUID(contacto_id)))
        return ContactoResponse(**resultado)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/", response_model=List[ContactoResponse])
async def listar_contactos(
    postulacion_id: Optional[str] = Query(None, title="ID de la postulación"),
    tipo_contacto: Optional[TipoContactoEnum] = Query(None, title="Tipo de mensaje"),
    leido: Optional[bool] = Query(None, title="Estado de lectura"),
    usuario: dict = Depends(obtener_usuario_actual)
):
    if not postulacion_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="postulacion_id es requerido"
        )

    try:
        postulacion_uuid = UUID(postulacion_id)
        postulacion = _obtener_postulacion_o_404(postulacion_uuid)
        _require_postulacion_access(postulacion, usuario)

        contacto_repository = ContactoRepositoryImpl()
        handler = ObtenerContactosPostulacionQueryHandler(contacto_repository)
        resultados = handler.handle(
            ObtenerContactosPostulacionQuery(postulacion_id=postulacion_uuid)
        )

        if tipo_contacto:
            resultados = [
                contacto for contacto in resultados
                if contacto.get("tipo_mensaje") == tipo_contacto.value
            ]

        if leido is not None:
            resultados = [
                contacto for contacto in resultados
                if bool(contacto.get("leido")) is leido
            ]

        return [ContactoResponse(**resultado) for resultado in resultados]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/feedback", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def enviar_feedback(
    feedback: FeedbackCreate,
    usuario: dict = Depends(obtener_usuario_actual)
):
    try:
        _require_role(usuario, "empresa")
        if str(feedback.empresa_id) != str(usuario.get("cuenta_id")):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No puedes enviar feedback como otra empresa"
            )

        postulacion_repository = PostulacionRepositoryImpl()
        postulacion = postulacion_repository.obtener_por_id(UUID(feedback.postulacion_id))
        if not postulacion:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Postulación con ID {feedback.postulacion_id} no encontrada"
            )

        _require_empresa_owner(postulacion, usuario)
        if str(postulacion.postulacion.candidato_id) != feedback.cuenta_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El postulante no corresponde a la postulación"
            )

        nuevo_estado = _estado_desde_feedback(feedback.tipo_feedback.value)
        if nuevo_estado and not postulacion.estado.es_valido(nuevo_estado):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La postulación no permite ese feedback en su estado actual"
            )

        contacto_repository = ContactoRepositoryImpl()
        handler = EnviarFeedbackCommandHandler(contacto_repository)
        comando = EnviarFeedbackCommand(
            postulacion_id=UUID(feedback.postulacion_id),
            empresa_id=UUID(feedback.empresa_id),
            cuenta_id=UUID(feedback.cuenta_id),
            tipo_feedback=feedback.tipo_feedback.value,
            mensaje_texto=feedback.mensaje_texto,
            motivo_rechazo=feedback.motivo_rechazo
        )
        resultado = handler.handle(comando)

        if nuevo_estado:
            estado_handler = ActualizarEstadoPostulacionHandler(postulacion_repository)
            estado_actualizado = estado_handler.handle(ActualizarEstadoCommand(
                postulacion_id=UUID(feedback.postulacion_id),
                nuevo_estado=nuevo_estado
            ))
            if not estado_actualizado:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No se pudo actualizar el estado desde el feedback"
                )

        return FeedbackResponse(
            feedback_id=str(resultado),
            postulacion_id=feedback.postulacion_id,
            tipo_feedback=feedback.tipo_feedback.value,
            mensaje=feedback.mensaje_texto,
            fecha_envio=datetime.now()
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
