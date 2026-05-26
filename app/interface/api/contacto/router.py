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
from app.infrastructure.contacto.repositories import ContactoRepositoryImpl
from app.infrastructure.postulacion.repositories import PostulacionRepositoryImpl
from app.infrastructure.puesto.repositories import PuestoRepositoryImpl
from app.interface.api.dependencies import obtener_usuario_actual

from .schemas import (
    ContactoCreate, ContactoResponse, ContactoUpdate,
    FeedbackCreate, FeedbackResponse, TipoContactoEnum
)

router = APIRouter(prefix="/contacto", tags=["Contacto"])


def _require_role(usuario: dict, rol: str) -> None:
    if usuario.get("rol") != rol:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Operacion permitida solo para rol {rol}"
        )


def _obtener_postulacion_o_404(postulacion_id: UUID):
    postulacion = PostulacionRepositoryImpl().obtener_por_id(postulacion_id)
    if not postulacion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Postulacion con ID {postulacion_id} no encontrada"
        )
    return postulacion


def _require_empresa_owner(postulacion, usuario: dict) -> None:
    _require_role(usuario, "empresa")
    puesto = PuestoRepositoryImpl().obtener_por_id(postulacion.postulacion.puesto_id)
    if not puesto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Puesto asociado a la postulacion no encontrado"
        )
    if str(puesto.puesto.empresa_id) != str(usuario.get("cuenta_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No puedes gestionar feedback de un puesto de otra empresa"
        )


def _require_postulacion_access(postulacion, usuario: dict) -> None:
    if usuario.get("rol") == "postulante":
        if str(postulacion.postulacion.candidato_id) != str(usuario.get("cuenta_id")):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No puedes consultar contactos de otra cuenta"
            )
        return

    if usuario.get("rol") == "empresa":
        _require_empresa_owner(postulacion, usuario)
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Rol no autorizado para contactos"
    )


def _estado_desde_feedback(tipo_feedback: str) -> Optional[str]:
    if tipo_feedback == "aprobacion":
        return "oferta"
    if tipo_feedback == "rechazo":
        return "rechazado"
    return None


@router.post("/", response_model=ContactoResponse, status_code=status.HTTP_201_CREATED)
async def crear_contacto(contacto: ContactoCreate):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Este endpoint esta temporalmente no disponible"
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
    postulacion_id: Optional[str] = Query(None, title="ID de la postulacion"),
    tipo_contacto: Optional[TipoContactoEnum] = Query(None, title="Tipo de contacto"),
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

        return [ContactoResponse(**resultado) for resultado in resultados]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.patch("/{contacto_id}", response_model=ContactoResponse)
async def actualizar_contacto(
    contacto_update: ContactoUpdate,
    contacto_id: str = Path(..., title="ID del contacto")
):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Este endpoint esta temporalmente no disponible"
    )


@router.patch("/{contacto_id}/leido", response_model=ContactoResponse)
async def marcar_contacto_leido(
    contacto_id: str = Path(..., title="ID del contacto")
):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Este endpoint esta temporalmente no disponible"
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
                detail=f"Postulacion con ID {feedback.postulacion_id} no encontrada"
            )

        _require_empresa_owner(postulacion, usuario)
        if str(postulacion.postulacion.candidato_id) != feedback.cuenta_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El candidato no corresponde a la postulacion"
            )

        nuevo_estado = _estado_desde_feedback(feedback.tipo_feedback.value)
        if nuevo_estado and not postulacion.estado.es_valido(nuevo_estado):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La postulacion no permite ese feedback en su estado actual"
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


@router.get("/feedback/{feedback_id}", response_model=FeedbackResponse)
async def obtener_feedback(feedback_id: str = Path(..., title="ID del feedback")):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Este endpoint esta temporalmente no disponible"
    )
