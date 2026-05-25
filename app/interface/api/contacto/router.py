from fastapi import APIRouter, Depends, HTTPException, status, Path, Query
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from app.application.contacto.command_handlers import (
    EnviarFeedbackCommandHandler, EnviarFeedbackCommand, 
    ActualizarEstadoContactoHandler
)
from app.application.contacto.query_handlers import (
    ObtenerContactoQueryHandler, ObtenerContactoQuery,
    ObtenerContactosPostulacionQueryHandler, ObtenerContactosPostulacionQuery
)
from app.infrastructure.contacto.repositories import ContactoRepositoryImpl

from .schemas import (
    ContactoCreate, ContactoResponse, ContactoUpdate,
    FeedbackCreate, FeedbackResponse, TipoContactoEnum
)

router = APIRouter(prefix="/contacto", tags=["Contacto"])

# Endpoints para Contactos
@router.post("/", response_model=ContactoResponse, status_code=status.HTTP_201_CREATED)
async def crear_contacto(contacto: ContactoCreate):
    # Desactivado temporalmente: handler no implementado
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Este endpoint está temporalmente no disponible"
    )


@router.get("/{contacto_id}", response_model=ContactoResponse)
async def obtener_contacto(contacto_id: str = Path(..., title="ID del contacto")):
    try:
        contacto_repository = ContactoRepositoryImpl()
        handler = ObtenerContactoQueryHandler(contacto_repository)
        resultado = handler.handle(ObtenerContactoQuery(contacto_id=UUID(contacto_id)))

        if not resultado:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Contacto con ID {contacto_id} no encontrado"
            )

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
    tipo_contacto: Optional[TipoContactoEnum] = Query(None, title="Tipo de contacto"),
    leido: Optional[bool] = Query(None, title="Estado de lectura")
):
    if not postulacion_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="postulacion_id es requerido"
        )

    try:
        contacto_repository = ContactoRepositoryImpl()
        handler = ObtenerContactosPostulacionQueryHandler(contacto_repository)
        resultados = handler.handle(
            ObtenerContactosPostulacionQuery(postulacion_id=UUID(postulacion_id))
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
    # Desactivado temporalmente: handler no implementado
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Este endpoint está temporalmente no disponible"
    )


@router.patch("/{contacto_id}/leido", response_model=ContactoResponse)
async def marcar_contacto_leido(
    contacto_id: str = Path(..., title="ID del contacto")
):
    # Desactivado temporalmente: handler no implementado
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Este endpoint está temporalmente no disponible"
    )


# Endpoints para Feedback
@router.post("/feedback", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def enviar_feedback(feedback: FeedbackCreate):
    try:
        contacto_repository = ContactoRepositoryImpl()
        handler = EnviarFeedbackCommandHandler(contacto_repository)
        # Ajustar los parámetros según la definición del handler real
        comando = EnviarFeedbackCommand(
            postulacion_id=UUID(feedback.postulacion_id),
            empresa_id=UUID(feedback.empresa_id),
            cuenta_id=UUID(feedback.cuenta_id),
            tipo_feedback=feedback.tipo_feedback.value,
            mensaje_texto=feedback.mensaje_texto,
            motivo_rechazo=feedback.motivo_rechazo
        )
        resultado = handler.handle(comando)
        
        # Construir respuesta
        respuesta = FeedbackResponse(
            feedback_id=str(resultado),
            postulacion_id=feedback.postulacion_id,
            tipo_feedback=feedback.tipo_feedback.value,
            mensaje=feedback.mensaje_texto,
            fecha_envio=datetime.now()
        )
        return respuesta
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/feedback/{feedback_id}", response_model=FeedbackResponse)
async def obtener_feedback(feedback_id: str = Path(..., title="ID del feedback")):
    # Desactivado temporalmente: handler no implementado
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Este endpoint está temporalmente no disponible"
    )
