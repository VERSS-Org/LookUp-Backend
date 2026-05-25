from fastapi import APIRouter, Depends, HTTPException, status, Path, Query
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from app.application.postulacion.command_handlers import (
    PostularHandler, PostularCommand,
    ActualizarEstadoPostulacionHandler, ActualizarEstadoCommand
)
from app.application.postulacion.postulacion_service import PostulacionService
from app.infrastructure.postulacion.repositories import PostulacionRepositoryImpl
from app.infrastructure.puesto.repositories import PuestoRepositoryImpl
from app.interface.api.dependencies import obtener_usuario_actual

from .schemas import (
    PostulacionCreate, PostulacionEnriquecidaResponse,
    EstadoUpdate, EstadoPostulacionEnum
)

router = APIRouter(prefix="/postulacion", tags=["Postulacion"])
postulacion_service = PostulacionService()


def _require_role(usuario: dict, rol: str) -> None:
    if usuario.get("rol") != rol:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Operacion permitida solo para rol {rol}"
        )


def _require_same_account(cuenta_id: UUID, usuario: dict) -> None:
    if str(cuenta_id) != str(usuario.get("cuenta_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No puedes operar con una cuenta distinta a la autenticada"
        )


def _serialize_postulacion(aggregate) -> dict:
    return {
        "postulacion_id": str(aggregate.postulacion.postulacion_id),
        "candidato_id": str(aggregate.postulacion.candidato_id),
        "puesto_id": str(aggregate.postulacion.puesto_id),
        "fecha_postulacion": aggregate.postulacion.fecha_postulacion.isoformat(),
        "estado": aggregate.postulacion.estado.valor.value,
        "documentos_adjuntos": aggregate.postulacion.documentos_adjuntos,
        "hitos": [
            {
                "hito_id": str(hito.hito_id),
                "fecha": hito.fecha.isoformat(),
                "descripcion": hito.descripcion
            }
            for hito in aggregate.linea_de_tiempo.lista_hitos
        ]
    }


def _obtener_puesto_o_404(puesto_id: UUID):
    puesto = PuestoRepositoryImpl().obtener_por_id(puesto_id)
    if not puesto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Puesto con ID {puesto_id} no encontrado"
        )
    return puesto


def _require_empresa_owner(puesto_id: UUID, usuario: dict) -> None:
    _require_role(usuario, "empresa")
    puesto = _obtener_puesto_o_404(puesto_id)
    if str(puesto.puesto.empresa_id) != str(usuario.get("cuenta_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No puedes gestionar postulaciones de un puesto de otra empresa"
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
    Crea una nueva postulacion para el postulante autenticado.
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

        respuesta_basica = {
            "postulacion_id": str(resultado),
            "candidato_id": postulacion.candidato_id,
            "puesto_id": postulacion.puesto_id,
            "fecha_postulacion": datetime.now().isoformat(),
            "estado": EstadoPostulacionEnum.PENDIENTE.value,
            "documentos_adjuntos": postulacion.documentos_adjuntos or [],
            "hitos": []
        }

        return postulacion_service.enriquecer_postulacion(respuesta_basica)
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


@router.get("/{postulacion_id}", response_model=PostulacionEnriquecidaResponse)
async def obtener_postulacion(
    postulacion_id: str = Path(..., title="ID de la postulacion"),
    usuario: dict = Depends(obtener_usuario_actual)
):
    """
    Obtiene una postulacion con datos enriquecidos si pertenece al usuario autenticado.
    """
    try:
        postulacion_repository = PostulacionRepositoryImpl()
        aggregate = postulacion_repository.obtener_por_id(UUID(postulacion_id))
        if aggregate is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Postulacion con ID {postulacion_id} no encontrada"
            )

        _require_postulacion_access(aggregate, usuario)
        return postulacion_service.enriquecer_postulacion(_serialize_postulacion(aggregate))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Postulacion con ID {postulacion_id} no encontrada"
        )


@router.get("/", response_model=List[PostulacionEnriquecidaResponse])
async def listar_postulaciones(
    candidato_id: Optional[str] = Query(None, title="ID del candidato"),
    puesto_id: Optional[str] = Query(None, title="ID del puesto"),
    estado: Optional[EstadoPostulacionEnum] = Query(None, title="Estado de la postulacion"),
    enriquecer: bool = Query(True, title="Incluir datos enriquecidos"),
    usuario: dict = Depends(obtener_usuario_actual)
):
    """
    Lista postulaciones por candidato o por puesto respetando la cuenta autenticada.
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
            resultados = [
                aggregate for aggregate in resultados
                if aggregate.postulacion.estado.valor.value == estado.value
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
    postulacion_id: str = Path(..., title="ID de la postulacion"),
    usuario: dict = Depends(obtener_usuario_actual)
):
    """
    Actualiza el estado de una postulacion solo si la empresa es duena del puesto.
    """
    try:
        postulacion_repository = PostulacionRepositoryImpl()
        postulacion_actual = postulacion_repository.obtener_por_id(UUID(postulacion_id))
        if not postulacion_actual:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Postulacion con ID {postulacion_id} no encontrada"
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
                detail="No se pudo actualizar el estado de la postulacion"
            )

        postulacion_actualizada = postulacion_repository.obtener_por_id(UUID(postulacion_id))
        if not postulacion_actualizada:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Postulacion con ID {postulacion_id} no encontrada"
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
