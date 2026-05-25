from fastapi import APIRouter, Depends, HTTPException, status, Path, Query
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from app.application.puesto.command_handlers import (
    CrearPuestoHandler, CrearPuestoCommand, ActualizarPuestoHandler,
    ActualizarPuestoCommand, CambiarEstadoPuestoHandler, CambiarEstadoPuestoCommand
)
from app.application.puesto.query_handlers import (
    ObtenerPuestoQueryHandler, ObtenerPuestoQuery,
    ListarPuestosQueryHandler, ListarPuestosQuery
)
from app.domain.puesto.entities import (
    EstadoPuestoEnum as DomainEstadoPuestoEnum,
    TipoContratoEnum as DomainTipoContratoEnum
)
from app.infrastructure.puesto.repositories import PuestoRepositoryImpl
from app.interface.api.dependencies import obtener_usuario_actual

from .schemas import (
    PuestoCreate, PuestoUpdate, PuestoResponse, RequisitoResponse,
    EstadoPuestoUpdate, EstadoPuestoEnum, TipoContratoEnum
)

router = APIRouter(prefix="/puesto", tags=["Puesto"])


def _require_empresa(usuario: dict) -> None:
    if usuario.get("rol") != "empresa":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operacion permitida solo para cuentas empresa"
        )


def _require_puesto_owner(puesto_id: UUID, usuario: dict, repository: PuestoRepositoryImpl):
    _require_empresa(usuario)
    puesto = repository.obtener_por_id(puesto_id)
    if not puesto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Puesto con ID {puesto_id} no encontrado"
        )
    if str(puesto.puesto.empresa_id) != str(usuario.get("cuenta_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No puedes modificar un puesto de otra empresa"
        )
    return puesto


def _parse_datetime(value, default=None):
    if isinstance(value, datetime):
        return value
    if value:
        return datetime.fromisoformat(value)
    return default


def _normalizar_requisitos(requisitos):
    return [
        RequisitoResponse(**req) if isinstance(req, dict) else req
        for req in (requisitos or [])
    ]


def _puesto_response(data: dict) -> PuestoResponse:
    return PuestoResponse(
        puesto_id=data.get("puesto_id", ""),
        empresa_id=data.get("empresa_id", ""),
        titulo=data.get("titulo", ""),
        descripcion=data.get("descripcion", ""),
        ubicacion=data.get("ubicacion", ""),
        salario_min=data.get("salario_min"),
        salario_max=data.get("salario_max"),
        moneda=data.get("moneda", "MXN"),
        tipo_contrato=data.get("tipo_contrato", "tiempo_completo"),
        fecha_publicacion=_parse_datetime(
            data.get("fecha_publicacion"),
            datetime.now()
        ),
        fecha_cierre=_parse_datetime(data.get("fecha_cierre")),
        estado=data.get("estado", EstadoPuestoEnum.ABIERTO.value),
        requisitos=_normalizar_requisitos(data.get("requisitos", []))
    )


@router.post("/", response_model=PuestoResponse, status_code=status.HTTP_201_CREATED)
async def crear_puesto(
    puesto: PuestoCreate,
    usuario: dict = Depends(obtener_usuario_actual)
):
    """
    Crea un nuevo puesto para la empresa autenticada.
    """
    try:
        _require_empresa(usuario)
        empresa_id = UUID(puesto.empresa_id)
        if str(empresa_id) != str(usuario.get("cuenta_id")):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No puedes crear puestos con una empresa distinta a la autenticada"
            )

        puesto_repository = PuestoRepositoryImpl()
        handler = CrearPuestoHandler(puesto_repository)

        requisitos = [
            {
                "tipo": req.tipo,
                "descripcion": req.descripcion,
                "es_obligatorio": req.es_obligatorio
            }
            for req in (puesto.requisitos or [])
        ]

        command = CrearPuestoCommand(
            empresa_id=empresa_id,
            titulo=puesto.titulo,
            descripcion=puesto.descripcion,
            ubicacion=puesto.ubicacion,
            salario_min=puesto.salario_min,
            salario_max=puesto.salario_max,
            moneda=puesto.moneda,
            tipo_contrato=DomainTipoContratoEnum(puesto.tipo_contrato.value),
            requisitos=requisitos if requisitos else None
        )
        resultado = handler.handle(command)
        return _puesto_response(resultado)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{puesto_id}", response_model=PuestoResponse)
async def obtener_puesto(puesto_id: str = Path(..., title="ID del puesto")):
    """
    Obtiene la informacion detallada de un puesto por su ID.
    """
    try:
        puesto_repository = PuestoRepositoryImpl()
        handler = ObtenerPuestoQueryHandler(puesto_repository)
        query = ObtenerPuestoQuery(puesto_id=UUID(puesto_id))
        resultado = handler.handle(query)
        if resultado is None:
            raise ValueError("No se encontro el puesto")
        return _puesto_response(resultado)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Puesto con ID {puesto_id} no encontrado"
        )


@router.get("/", response_model=List[PuestoResponse])
async def listar_puestos(
    empresa_id: Optional[str] = Query(None, title="ID de la empresa"),
    estado: Optional[EstadoPuestoEnum] = Query(None, title="Estado del puesto (abierto/cerrado)")
):
    """
    Lista puestos con filtros publicos opcionales.
    """
    try:
        puesto_repository = PuestoRepositoryImpl()
        handler = ListarPuestosQueryHandler(puesto_repository)
        query = ListarPuestosQuery(
            empresa_id=UUID(empresa_id) if empresa_id else None,
            estado=estado
        )
        return [_puesto_response(resultado) for resultado in handler.handle(query)]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.put("/{puesto_id}", response_model=PuestoResponse)
async def actualizar_puesto(
    puesto_update: PuestoUpdate,
    puesto_id: str = Path(..., title="ID del puesto"),
    usuario: dict = Depends(obtener_usuario_actual)
):
    """
    Actualiza un puesto existente solo si pertenece a la empresa autenticada.
    """
    try:
        puesto_repository = PuestoRepositoryImpl()
        _require_puesto_owner(UUID(puesto_id), usuario, puesto_repository)

        handler = ActualizarPuestoHandler(puesto_repository)
        requisitos = None
        if puesto_update.requisitos is not None:
            requisitos = [
                req.dict() if hasattr(req, "dict") else req
                for req in puesto_update.requisitos
            ]

        tipo_contrato = None
        if puesto_update.tipo_contrato:
            tipo_contrato = DomainTipoContratoEnum(puesto_update.tipo_contrato.value)

        resultado = handler.handle(ActualizarPuestoCommand(
            puesto_id=UUID(puesto_id),
            titulo=puesto_update.titulo,
            descripcion=puesto_update.descripcion,
            ubicacion=puesto_update.ubicacion,
            salario_min=puesto_update.salario_min,
            salario_max=puesto_update.salario_max,
            moneda=puesto_update.moneda,
            tipo_contrato=tipo_contrato,
            requisitos=requisitos
        ))

        return _puesto_response(resultado)
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


@router.patch("/{puesto_id}/estado", response_model=PuestoResponse)
async def cambiar_estado_puesto(
    estado_update: EstadoPuestoUpdate,
    puesto_id: str = Path(..., title="ID del puesto"),
    usuario: dict = Depends(obtener_usuario_actual)
):
    """
    Cambia el estado de un puesto solo si pertenece a la empresa autenticada.
    """
    try:
        puesto_repository = PuestoRepositoryImpl()
        handler_get = ObtenerPuestoQueryHandler(puesto_repository)
        query_get = ObtenerPuestoQuery(puesto_id=UUID(puesto_id))
        puesto_actual = handler_get.handle(query_get)
        if not puesto_actual:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Puesto con ID {puesto_id} no encontrado"
            )

        _require_puesto_owner(UUID(puesto_id), usuario, puesto_repository)

        handler = CambiarEstadoPuestoHandler(puesto_repository)
        resultado = handler.handle(CambiarEstadoPuestoCommand(
            puesto_id=UUID(puesto_id),
            nuevo_estado=DomainEstadoPuestoEnum(estado_update.nuevo_estado.value)
        ))

        return _puesto_response({**puesto_actual, **resultado})
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
