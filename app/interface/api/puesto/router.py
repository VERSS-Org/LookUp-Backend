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
from app.infrastructure.database.connection import SessionLocal
from app.infrastructure.iam.models import CuentaModel
from app.infrastructure.postulacion.models import PostulacionModel
from app.infrastructure.puesto.repositories import PuestoRepositoryImpl
from app.interface.api.dependencies import obtener_usuario_actual

from .schemas import (
    PuestoCreate, PuestoUpdate, PuestoResponse, RequisitoResponse,
    EstadoPuestoUpdate, EstadoPuestoEnum
)

router = APIRouter(prefix="/puesto", tags=["Vacantes"])


def _require_empresa(usuario: dict) -> None:
    if usuario.get("rol") != "empresa":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operación permitida solo para cuentas de empresa"
        )


def _require_puesto_owner(puesto_id: UUID, usuario: dict, repository: PuestoRepositoryImpl):
    _require_empresa(usuario)
    puesto = repository.obtener_por_id(puesto_id)
    if not puesto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vacante con ID {puesto_id} no encontrada"
        )
    if str(puesto.puesto.empresa_id) != str(usuario.get("cuenta_id")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No puedes modificar una vacante de otra empresa"
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


def _empresas_info(empresa_ids: set) -> dict:
    """Nombre y foto de cada empresa, para mostrar en las vacantes."""
    if not empresa_ids:
        return {}
    db = SessionLocal()
    try:
        cuentas = db.query(CuentaModel).filter(
            CuentaModel.id.in_(empresa_ids)
        ).all()
        return {
            str(c.id): {"nombre": c.nombre_completo, "foto": c.foto_url}
            for c in cuentas
        }
    finally:
        db.close()


def _adjuntar_empresa(respuestas: list) -> list:
    infos = _empresas_info({r.empresa_id for r in respuestas if r.empresa_id})
    for r in respuestas:
        info = infos.get(r.empresa_id)
        if info:
            r.empresa_nombre = info["nombre"]
            r.empresa_foto = info["foto"]
    return respuestas


def _puesto_response(data: dict) -> PuestoResponse:
    return PuestoResponse(
        puesto_id=data.get("puesto_id", ""),
        empresa_id=data.get("empresa_id", ""),
        titulo=data.get("titulo", ""),
        descripcion=data.get("descripcion", ""),
        ubicacion=data.get("ubicacion", ""),
        salario_min=data.get("salario_min"),
        salario_max=data.get("salario_max"),
        moneda=data.get("moneda", "PEN"),
        tipo_contrato=data.get("tipo_contrato", "tiempo_completo"),
        fecha_publicacion=_parse_datetime(
            data.get("fecha_publicacion"),
            datetime.now()
        ),
        fecha_cierre=_parse_datetime(data.get("fecha_cierre")),
        estado=data.get("estado", EstadoPuestoEnum.ABIERTO.value),
        requisitos=_normalizar_requisitos(data.get("requisitos", []))
    )


@router.post(
    "/",
    response_model=PuestoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear vacante",
)
async def crear_puesto(
    puesto: PuestoCreate,
    usuario: dict = Depends(obtener_usuario_actual)
):
    """
    Crea una nueva vacante para la empresa autenticada.
    """
    try:
        _require_empresa(usuario)
        empresa_id = UUID(puesto.empresa_id)
        if str(empresa_id) != str(usuario.get("cuenta_id")):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No puedes crear vacantes con una empresa distinta a la autenticada"
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


@router.get(
    "/{puesto_id}",
    response_model=PuestoResponse,
    summary="Obtener detalle de vacante",
)
async def obtener_puesto(
    puesto_id: str = Path(..., title="ID de la vacante"),
    usuario: dict = Depends(obtener_usuario_actual),
):
    """
    Obtiene la informacion detallada de una vacante por su ID.
    """
    try:
        puesto_repository = PuestoRepositoryImpl()
        handler = ObtenerPuestoQueryHandler(puesto_repository)
        query = ObtenerPuestoQuery(puesto_id=UUID(puesto_id))
        resultado = handler.handle(query)
        if resultado is None:
            raise ValueError("No se encontró la vacante")

        if usuario.get("rol") == "empresa":
            if resultado["empresa_id"] != str(usuario.get("cuenta_id")):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No puedes consultar una vacante de otra empresa",
                )
        elif usuario.get("rol") == "postulante":
            if resultado["estado"] != EstadoPuestoEnum.ABIERTO.value:
                db = SessionLocal()
                try:
                    tiene_postulacion = db.query(PostulacionModel.id).filter(
                        PostulacionModel.puesto_id == puesto_id,
                        PostulacionModel.cuenta_id == str(usuario["cuenta_id"]),
                    ).first()
                finally:
                    db.close()
                if not tiene_postulacion:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Esta vacante ya no está disponible",
                    )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Rol no autorizado para consultar vacantes",
            )
        return _adjuntar_empresa([_puesto_response(resultado)])[0]
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vacante con ID {puesto_id} no encontrada"
        )


@router.get(
    "/",
    response_model=List[PuestoResponse],
    summary="Listar vacantes",
)
async def listar_puestos(
    empresa_id: Optional[str] = Query(None, title="ID de la empresa"),
    estado: Optional[EstadoPuestoEnum] = Query(None, title="Estado de la vacante (abierto/cerrado)"),
    usuario: dict = Depends(obtener_usuario_actual)
):
    """
    Lista vacantes respetando el rol autenticado.
    """
    try:
        empresa_uuid = UUID(empresa_id) if empresa_id else None
        estado_filtro = estado

        if usuario.get("rol") == "empresa":
            if empresa_uuid is None:
                empresa_uuid = UUID(usuario["cuenta_id"])
            elif str(empresa_uuid) != str(usuario.get("cuenta_id")):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No puedes listar vacantes de otra empresa"
                )
        elif usuario.get("rol") == "postulante":
            estado_filtro = EstadoPuestoEnum.ABIERTO
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Rol no autorizado para listar vacantes"
            )

        puesto_repository = PuestoRepositoryImpl()
        handler = ListarPuestosQueryHandler(puesto_repository)
        query = ListarPuestosQuery(
            empresa_id=empresa_uuid,
            estado=estado_filtro
        )
        respuestas = [
            _puesto_response(resultado) for resultado in handler.handle(query)
        ]
        return _adjuntar_empresa(respuestas)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.put(
    "/{puesto_id}",
    response_model=PuestoResponse,
    summary="Actualizar vacante",
)
async def actualizar_puesto(
    puesto_update: PuestoUpdate,
    puesto_id: str = Path(..., title="ID de la vacante"),
    usuario: dict = Depends(obtener_usuario_actual)
):
    """
    Actualiza una vacante solo si pertenece a la empresa autenticada.
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

        campos_enviados = getattr(
            puesto_update,
            "model_fields_set",
            getattr(puesto_update, "__fields_set__", set()),
        )

        resultado = handler.handle(ActualizarPuestoCommand(
            puesto_id=UUID(puesto_id),
            titulo=puesto_update.titulo,
            descripcion=puesto_update.descripcion,
            ubicacion=puesto_update.ubicacion,
            salario_min=puesto_update.salario_min,
            salario_max=puesto_update.salario_max,
            actualizar_salario_min="salario_min" in campos_enviados,
            actualizar_salario_max="salario_max" in campos_enviados,
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


@router.patch(
    "/{puesto_id}/estado",
    response_model=PuestoResponse,
    summary="Cambiar estado de vacante",
)
async def cambiar_estado_puesto(
    estado_update: EstadoPuestoUpdate,
    puesto_id: str = Path(..., title="ID de la vacante"),
    usuario: dict = Depends(obtener_usuario_actual)
):
    """
    Cambia el estado de una vacante solo si pertenece a la empresa autenticada.
    """
    try:
        puesto_repository = PuestoRepositoryImpl()
        handler_get = ObtenerPuestoQueryHandler(puesto_repository)
        query_get = ObtenerPuestoQuery(puesto_id=UUID(puesto_id))
        puesto_actual = handler_get.handle(query_get)
        if not puesto_actual:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vacante con ID {puesto_id} no encontrada"
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
