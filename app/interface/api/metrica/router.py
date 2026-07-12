from fastapi import APIRouter, Depends, HTTPException, status, Path
from typing import List
from uuid import UUID

from app.application.metrica.command_handlers import (
    RecalcularMetricasCommand, RecalcularMetricasHandler
)
from app.application.metrica.query_handlers import (
    ConsultarResumenMetricasQuery, ConsultarResumenMetricasHandler,
    ListarLogrosQuery, ListarLogrosHandler,
    ContadorAceptacionesQuery, ContadorAceptacionesQueryHandler,
    ContadorEntrevistasQuery, ContadorEntrevistasQueryHandler,
    ContadorRechazosQuery, ContadorRechazosQueryHandler
)
from app.infrastructure.metrica.repositories import MetricaRepositoryImpl
from app.interface.api.dependencies import obtener_usuario_actual

from .schemas import (
    MetricaResumenResponse,
    LogroResponse,
    ContadorResponse
)

router = APIRouter(prefix="/metricas", tags=["Métricas"])


def _require_metric_owner(cuenta_id: UUID, usuario: dict) -> None:
    if usuario.get("rol") != "postulante":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Las métricas corresponden a cuentas de postulante",
        )
    if str(cuenta_id) != str(usuario.get("cuenta_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No puedes consultar métricas de otra cuenta"
        )


@router.get("/resumen/{cuenta_id}", response_model=MetricaResumenResponse)
async def obtener_resumen_metricas(
    cuenta_id: UUID = Path(..., title="ID de la cuenta"),
    usuario: dict = Depends(obtener_usuario_actual)
):
    """
    Obtiene un resumen de métricas para la cuenta autenticada.
    """
    try:
        _require_metric_owner(cuenta_id, usuario)
        metrica_repository = MetricaRepositoryImpl()
        handler = ConsultarResumenMetricasHandler(metrica_repository)
        query = ConsultarResumenMetricasQuery(cuenta_id=cuenta_id)

        resultado = handler.handle(query)
        if not resultado:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontraron métricas para la cuenta {cuenta_id}"
            )
        return resultado
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/logros/{cuenta_id}", response_model=List[LogroResponse])
async def listar_logros(
    cuenta_id: UUID = Path(..., title="ID de la cuenta"),
    usuario: dict = Depends(obtener_usuario_actual)
):
    """
    Lista los logros conseguidos por la cuenta autenticada.
    """
    try:
        _require_metric_owner(cuenta_id, usuario)
        metrica_repository = MetricaRepositoryImpl()
        handler = ListarLogrosHandler(metrica_repository)
        query = ListarLogrosQuery(cuenta_id=cuenta_id)

        return handler.handle(query)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/recalcular/{cuenta_id}", response_model=MetricaResumenResponse)
async def recalcular_metricas(
    cuenta_id: UUID = Path(..., title="ID de la cuenta"),
    usuario: dict = Depends(obtener_usuario_actual)
):
    """
    Fuerza un recálculo de métricas para la cuenta autenticada.
    """
    try:
        _require_metric_owner(cuenta_id, usuario)
        metrica_repository = MetricaRepositoryImpl()
        handler = RecalcularMetricasHandler(metrica_repository)
        command = RecalcularMetricasCommand(cuenta_id=cuenta_id)

        return handler.handle(command)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/contadores/ofertas/{postulante_id}",
    response_model=ContadorResponse,
    summary="Contador de postulaciones aceptadas",
)
async def obtener_contador_aceptaciones(
    postulante_id: UUID = Path(..., title="ID del postulante"),
    usuario: dict = Depends(obtener_usuario_actual)
):
    """
    Obtiene el contador de postulaciones aceptadas para el postulante autenticado.
    """
    try:
        _require_metric_owner(postulante_id, usuario)
        metrica_repository = MetricaRepositoryImpl()
        handler = ContadorAceptacionesQueryHandler(metrica_repository)
        query = ContadorAceptacionesQuery(postulante_id=postulante_id)

        result = handler.handle(query)
        return {
            "postulante_id": result["postulante_id"],
            "total": result["total_aceptaciones"]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/contadores/entrevistas/{postulante_id}", response_model=ContadorResponse)
async def obtener_contador_entrevistas(
    postulante_id: UUID = Path(..., title="ID del postulante"),
    usuario: dict = Depends(obtener_usuario_actual)
):
    """
    Obtiene el contador de entrevistas para el postulante autenticado.
    """
    try:
        _require_metric_owner(postulante_id, usuario)
        metrica_repository = MetricaRepositoryImpl()
        handler = ContadorEntrevistasQueryHandler(metrica_repository)
        query = ContadorEntrevistasQuery(postulante_id=postulante_id)

        result = handler.handle(query)
        return {
            "postulante_id": result["postulante_id"],
            "total": result["total_entrevistas"]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/contadores/rechazos/{postulante_id}", response_model=ContadorResponse)
async def obtener_contador_rechazos(
    postulante_id: UUID = Path(..., title="ID del postulante"),
    usuario: dict = Depends(obtener_usuario_actual)
):
    """
    Obtiene el contador de rechazos para el postulante autenticado.
    """
    try:
        _require_metric_owner(postulante_id, usuario)
        metrica_repository = MetricaRepositoryImpl()
        handler = ContadorRechazosQueryHandler(metrica_repository)
        query = ContadorRechazosQuery(postulante_id=postulante_id)

        result = handler.handle(query)
        return {
            "postulante_id": result["postulante_id"],
            "total": result["total_rechazos"]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
