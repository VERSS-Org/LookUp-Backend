import hashlib
import hmac
import secrets

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from typing import Optional
from datetime import datetime, timedelta
from pathlib import Path as FilePath
from urllib.parse import urlparse
from uuid import UUID
from uuid import uuid4

from app.application.iam.command_handlers import (
    CrearCuentaHandler, CrearCuentaCommand,
    LoginHandler, LoginCommand,
    GenerarTokenHandler, GenerarTokenCommand,
    CambiarPasswordHandler, CambiarPasswordCommand
)
from app.application.iam.query_handlers import (
    ObtenerCuentaQueryHandler, ObtenerCuentaQuery,
    ObtenerCuentaPorEmailQueryHandler, ObtenerCuentaPorEmailQuery,
    VerificarTokenQueryHandler, VerificarTokenQuery
)
from app.config import settings
from app.domain.iam.privacy import email_visible_para_usuario
from app.infrastructure.database.connection import SessionLocal
from app.infrastructure.iam.models import CuentaModel, TokenModel
from app.infrastructure.iam.repositories import CuentaRepositoryImpl
from app.infrastructure.iam.security import PasswordManager, TokenManager
from app.infrastructure.postulacion.models import PostulacionModel
from app.infrastructure.puesto.models import PuestoMapeo, PuestoModel
from app.interface.api.dependencies import obtener_usuario_actual

from .schemas import (
    CrearCuentaRequest, LoginRequest,
    RecuperarPasswordRequest, RestablecerPasswordRequest, RecuperacionResponse,
    RefreshTokenRequest, CambiarPasswordRequest, CuentaUpdateRequest,
    TokenResponse, CuentaResponse,
    MensajeResponse, TokenVerificationResponse
)

router = APIRouter(prefix="/iam", tags=["IAM"])
PROJECT_ROOT = FilePath(__file__).resolve().parents[4]
PROFILE_PHOTO_DIR = PROJECT_ROOT / "uploads" / "profile_photos"
MAX_PROFILE_PHOTO_BYTES = 3 * 1024 * 1024
ALLOWED_PROFILE_PHOTO_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
}


def _looks_like_image(content: bytes, extension: str) -> bool:
    if extension in {".jpg", ".jpeg"}:
        return content.startswith(b"\xff\xd8\xff")
    if extension == ".png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    if extension == ".webp":
        return len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP"
    if extension == ".gif":
        return content.startswith((b"GIF87a", b"GIF89a"))
    return False


def _validar_misma_cuenta(cuenta_id: str, usuario: dict) -> None:
    if str(usuario.get("cuenta_id")) != str(cuenta_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para modificar esta cuenta"
        )


def _validar_acceso_lectura_cuenta(cuenta_data: dict, usuario: dict) -> None:
    """Protege perfiles completos sin romper sus usos legitimos en reclutamiento."""
    cuenta_objetivo = str(cuenta_data["cuenta_id"])
    cuenta_actual = str(usuario.get("cuenta_id"))
    if cuenta_objetivo == cuenta_actual:
        return

    if (
        not cuenta_data.get("activa", True)
        or cuenta_data.get("estado") in {"inactiva", "suspendida"}
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cuenta no encontrada",
        )

    rol_actual = usuario.get("rol")
    rol_objetivo = cuenta_data.get("rol")

    # Los perfiles de empresa son visibles para postulantes autenticados.
    if rol_actual == "postulante" and rol_objetivo == "empresa":
        return

    # Una empresa solo puede ver el perfil completo de quienes postularon a
    # alguna de sus propias vacantes.
    if rol_actual == "empresa" and rol_objetivo == "postulante":
        db = SessionLocal()
        try:
            postulacion = (
                db.query(PostulacionModel.id)
                .join(
                    PuestoMapeo,
                    PuestoMapeo.uuid_id == PostulacionModel.puesto_id,
                )
                .join(PuestoModel, PuestoModel.id == PuestoMapeo.bd_id)
                .filter(
                    PostulacionModel.cuenta_id == cuenta_objetivo,
                    PuestoModel.empresa == cuenta_actual,
                )
                .first()
            )
        finally:
            db.close()
        if postulacion:
            return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No tienes permiso para consultar el perfil completo de esta cuenta",
    )


def _aplicar_privacidad_email(cuenta_data: dict, usuario: dict) -> dict:
    """Devuelve una copia apta para el solicitante sin mutar la consulta."""

    respuesta = cuenta_data.copy()
    if not email_visible_para_usuario(cuenta_data, usuario):
        respuesta["email"] = None
    return respuesta


def _eliminar_foto_local(foto_url: Optional[str], cuenta_id: str) -> None:
    if not foto_url:
        return
    nombre = FilePath(urlparse(foto_url).path).name
    if not nombre.startswith(f"{cuenta_id}-"):
        return
    ruta = PROFILE_PHOTO_DIR / nombre
    if ruta.is_file():
        ruta.unlink()


@router.post("/registrar", response_model=CuentaResponse, status_code=status.HTTP_201_CREATED)
async def registrar_cuenta(request: CrearCuentaRequest):
    """
    Registra una nueva cuenta de usuario.
    - **email**: Email único del usuario
    - **password**: Contraseña (mín. 8 caracteres, mayúscula, minúscula, número, carácter especial)
    - **rol**: Tipo de cuenta (`postulante` o `empresa`)
    """
    try:
        repository = CuentaRepositoryImpl()
        handler = CrearCuentaHandler(repository)
        
        command = CrearCuentaCommand(
            nombre_completo=request.nombre_completo,
            email=request.email,
            password=request.password,
            carrera=request.carrera,
            telefono=request.telefono,
            ciudad=request.ciudad,
            rol=request.rol
        )
        
        cuenta_id = handler.handle(command)
        
        # Obtener la cuenta creada para devolver los datos completos
        query_handler = ObtenerCuentaQueryHandler(repository)
        cuenta_data = query_handler.handle(ObtenerCuentaQuery(cuenta_id=UUID(cuenta_id['cuenta_id'])))
        
        return CuentaResponse(
            cuenta_id=cuenta_data['cuenta_id'],
            nombre_completo=cuenta_data['nombre_completo'],
            email=cuenta_data['email'],
            carrera=cuenta_data['carrera'],
            telefono=cuenta_data['telefono'],
            ciudad=cuenta_data['ciudad'],
            foto_url=cuenta_data.get('foto_url'),
            perfil=cuenta_data.get('perfil'),
            rol=cuenta_data['rol'],
            estado=cuenta_data['estado'],
            fecha_creacion=cuenta_data['fecha_creacion'],
            fecha_actualizacion=cuenta_data['fecha_actualizacion'],
            fecha_primer_acceso=cuenta_data['fecha_primer_acceso']
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
            detail=f"Error al registrar cuenta: {str(e)}"
        )


@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def login(request: LoginRequest):
    """
    Realiza login del usuario y devuelve tokens JWT.
    
    - **email**: Email del usuario
    - **password**: Contraseña del usuario
    
    Retorna access_token y refresh_token para futuras autenticaciones.
    """
    try:
        repository = CuentaRepositoryImpl()
        handler = LoginHandler(repository)
        
        command = LoginCommand(
            email=request.email,
            password=request.password
        )
        
        resultado = handler.handle(command)
        
        return TokenResponse(
            access_token=resultado['access_token'],
            refresh_token=resultado['refresh_token'],
            token_type=resultado['token_type'],
            cuenta_id=resultado['cuenta_id'],
            email=resultado['email'],
            rol=resultado['rol']
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error en login: {str(e)}"
        )


@router.post("/refresh-token", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def refresh_token(request: RefreshTokenRequest):
    """
    Obtiene un nuevo access_token usando el refresh_token.
    
    - **refresh_token**: Token de refresco obtenido en el login
    """
    try:
        # Verificar el refresh token
        payload = TokenManager.verificar_token(request.refresh_token)
        
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de refresco inválido o expirado"
            )
        
        if payload.get("tipo") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Tipo de token incorrecto"
            )

        cuenta_id = payload.get("sub")
        try:
            cuenta_uuid = UUID(cuenta_id)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de refresco sin una cuenta válida",
            )

        db = SessionLocal()
        try:
            token_persistido = db.query(TokenModel).filter(
                TokenModel.cuenta_id == cuenta_uuid,
                TokenModel.token_value == request.refresh_token,
                TokenModel.tipo_token == "refresh",
                TokenModel.activo.is_(True),
            ).first()
            if not token_persistido or (
                token_persistido.fecha_expiracion
                and token_persistido.fecha_expiracion < datetime.now()
            ):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token de refresco revocado o expirado",
                )
        finally:
            db.close()
        
        # Obtener la cuenta
        repository = CuentaRepositoryImpl()
        query_handler = ObtenerCuentaQueryHandler(repository)
        query = ObtenerCuentaQuery(cuenta_id=cuenta_uuid)
        cuenta_data = query_handler.handle(query)
        
        if not cuenta_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cuenta no encontrada"
            )

        if (
            not cuenta_data.get("activa", True)
            or cuenta_data["estado"] in {"inactiva", "suspendida"}
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="La cuenta no está habilitada",
            )
        
        token_resultado = GenerarTokenHandler(repository).handle(
            GenerarTokenCommand(
                cuenta_id=cuenta_uuid,
                tipo_token="access",
            )
        )
        nuevo_access_token = token_resultado["token"]
        
        return TokenResponse(
            access_token=nuevo_access_token,
            token_type="bearer",
            cuenta_id=payload.get("sub"),
            email=cuenta_data.get("email"),
            rol=cuenta_data.get("rol")
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al refrescar token: {str(e)}"
        )


@router.post("/cambiar-password", response_model=MensajeResponse, status_code=status.HTTP_200_OK)
async def cambiar_password(
    request: CambiarPasswordRequest,
    cuenta_id: Optional[str] = None,
    usuario: dict = Depends(obtener_usuario_actual)
):
    """
    Cambia la contraseña del usuario autenticado.
    
    - **password_actual**: Contraseña actual
    - **password_nuevo**: Nueva contraseña
    - **cuenta_id**: ID de la cuenta (desde header o parámetro)
    """
    try:
        cuenta_objetivo = cuenta_id or usuario["cuenta_id"]
        _validar_misma_cuenta(cuenta_objetivo, usuario)

        repository = CuentaRepositoryImpl()
        handler = CambiarPasswordHandler(repository)
        
        command = CambiarPasswordCommand(
            cuenta_id=UUID(cuenta_objetivo),
            password_actual=request.password_actual,
            password_nuevo=request.password_nuevo
        )
        
        handler.handle(command)
        
        return MensajeResponse(
            mensaje="Contraseña actualizada exitosamente",
            exito=True
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
            detail=f"Error al cambiar contraseña: {str(e)}"
        )


RESET_CODE_TTL_MINUTES = 15


def _reset_token_value(cuenta_id: UUID, codigo: str) -> str:
    digest = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        f"{cuenta_id}:{codigo}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"reset:{cuenta_id}:{digest}"


@router.post("/recuperar-password", response_model=RecuperacionResponse, status_code=status.HTTP_200_OK)
async def recuperar_password(request: RecuperarPasswordRequest):
    """
    Genera un código de recuperación de contraseña de 6 dígitos válido por
    15 minutos. La respuesta es neutra (no revela si la cuenta existe).

    Para pruebas locales sin correo, `codigo_dev` solo se devuelve cuando
    `EXPOSE_RESET_CODE=true` y el entorno es de desarrollo.
    """
    mensaje = (
        "Si el correo está registrado, recibirás un código para restablecer "
        "tu contraseña."
    )
    try:
        repository = CuentaRepositoryImpl()
        cuenta = repository.obtener_por_email(request.email)
        if not cuenta:
            return RecuperacionResponse(mensaje=mensaje)

        codigo = f"{secrets.randbelow(1_000_000):06d}"
        cuenta_id = cuenta.cuenta.cuenta_id

        db = SessionLocal()
        try:
            # Invalidar códigos anteriores de esta cuenta.
            db.query(TokenModel).filter(
                TokenModel.cuenta_id == cuenta_id,
                TokenModel.tipo_token == "reset",
                TokenModel.activo.is_(True),
            ).update({TokenModel.activo: False}, synchronize_session=False)

            db.add(TokenModel(
                cuenta_id=cuenta_id,
                # token_value es único: se combina con la cuenta.
                token_value=_reset_token_value(cuenta_id, codigo),
                tipo_token="reset",
                fecha_creacion=datetime.now(),
                fecha_expiracion=datetime.now() + timedelta(
                    minutes=RESET_CODE_TTL_MINUTES),
                activo=True,
            ))
            db.commit()
        finally:
            db.close()

        codigo_dev = (
            codigo
            if settings.ENVIRONMENT == "development"
            and settings.EXPOSE_RESET_CODE
            else None
        )
        return RecuperacionResponse(mensaje=mensaje, codigo_dev=codigo_dev)
    except HTTPException:
        raise
    except Exception:
        # Respuesta neutra incluso ante errores para no filtrar información.
        return RecuperacionResponse(mensaje=mensaje)


@router.post("/restablecer-password", response_model=MensajeResponse, status_code=status.HTTP_200_OK)
async def restablecer_password(request: RestablecerPasswordRequest):
    """
    Restablece la contraseña usando el código de recuperación vigente.
    """
    error_generico = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Código inválido o expirado"
    )
    try:
        repository = CuentaRepositoryImpl()
        cuenta_aggregate = repository.obtener_por_email(request.email)
        if not cuenta_aggregate:
            raise error_generico

        cuenta_id = cuenta_aggregate.cuenta.cuenta_id
        codigo = request.codigo.strip()
        token_esperado = _reset_token_value(cuenta_id, codigo)
        token_legado = f"reset:{cuenta_id}:{codigo}"

        db = SessionLocal()
        try:
            token = db.query(TokenModel).filter(
                TokenModel.cuenta_id == cuenta_id,
                TokenModel.tipo_token == "reset",
                TokenModel.activo.is_(True),
                TokenModel.token_value.in_((token_esperado, token_legado)),
            ).first()
            if not token or (
                token.fecha_expiracion
                and token.fecha_expiracion < datetime.now()
            ):
                raise error_generico

            if not PasswordManager.es_password_fuerte(request.password_nuevo):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "La contraseña debe tener al menos 8 caracteres, una "
                        "mayúscula, una minúscula, un número y un carácter "
                        "especial"
                    )
                )

            token.activo = False
            db.commit()
        finally:
            db.close()

        nuevo_hash = PasswordManager.hashear_password(request.password_nuevo)
        cuenta_aggregate.aplicar_cambio_password(nuevo_hash)
        repository.guardar(cuenta_aggregate)
        repository.revocar_tokens(cuenta_id)

        return MensajeResponse(
            mensaje="Contraseña restablecida correctamente", exito=True
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al restablecer contraseña: {str(e)}"
        )


@router.get("/empresas", status_code=status.HTTP_200_OK)
async def buscar_empresas(
    q: Optional[str] = None,
    usuario: dict = Depends(obtener_usuario_actual)
):
    """
    Lista empresas registradas (búsqueda pública para usuarios autenticados).
    - **q**: filtro opcional por nombre.
    """
    import json as _json
    from app.domain.iam.entities import EstadoCuentaEnum, RolEnum

    db = SessionLocal()
    try:
        query = db.query(CuentaModel).filter(
            CuentaModel.rol == RolEnum.EMPRESA,
            CuentaModel.activa.is_(True),
            CuentaModel.estado.notin_((
                EstadoCuentaEnum.INACTIVA,
                EstadoCuentaEnum.SUSPENDIDA,
            )),
        )
        if q:
            query = query.filter(CuentaModel.nombre_completo.ilike(f"%{q.strip()}%"))
        cuentas = query.order_by(CuentaModel.nombre_completo.asc()).limit(50).all()

        resultado = []
        for cuenta in cuentas:
            descripcion = None
            if getattr(cuenta, "perfil", None):
                try:
                    descripcion = _json.loads(cuenta.perfil).get("descripcion")
                except Exception:
                    descripcion = None
            resultado.append({
                "cuenta_id": str(cuenta.id),
                "nombre": cuenta.nombre_completo,
                "foto_url": cuenta.foto_url,
                "ciudad": cuenta.ciudad,
                "descripcion": descripcion,
            })
        return resultado
    finally:
        db.close()


@router.get("/me", response_model=CuentaResponse, status_code=status.HTTP_200_OK)
async def obtener_mi_cuenta(usuario: dict = Depends(obtener_usuario_actual)):
    """
    Obtiene la cuenta asociada al token actual.
    """
    try:
        repository = CuentaRepositoryImpl()
        handler = ObtenerCuentaQueryHandler(repository)
        cuenta_data = handler.handle(ObtenerCuentaQuery(cuenta_id=UUID(usuario["cuenta_id"])))

        if not cuenta_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cuenta no encontrada"
            )

        return CuentaResponse(**cuenta_data)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al obtener cuenta: {str(e)}"
        )


@router.get("/cuenta/{cuenta_id}", response_model=CuentaResponse, status_code=status.HTTP_200_OK)
async def obtener_cuenta(
    cuenta_id: str,
    usuario: dict = Depends(obtener_usuario_actual),
):
    """
    Obtiene la información de una cuenta.
    
    - **cuenta_id**: ID de la cuenta
    """
    try:
        repository = CuentaRepositoryImpl()
        handler = ObtenerCuentaQueryHandler(repository)
        
        query = ObtenerCuentaQuery(cuenta_id=UUID(cuenta_id))
        cuenta_data = handler.handle(query)
        
        if not cuenta_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cuenta no encontrada: {cuenta_id}"
            )

        _validar_acceso_lectura_cuenta(cuenta_data, usuario)
        return CuentaResponse(**_aplicar_privacidad_email(cuenta_data, usuario))
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al obtener cuenta: {str(e)}"
        )


@router.patch("/cuenta/{cuenta_id}", response_model=CuentaResponse, status_code=status.HTTP_200_OK)
async def actualizar_cuenta(
    request: CuentaUpdateRequest,
    cuenta_id: str,
    usuario: dict = Depends(obtener_usuario_actual)
):
    """
    Actualiza los datos editables de la cuenta autenticada.
    """
    try:
        _validar_misma_cuenta(cuenta_id, usuario)

        repository = CuentaRepositoryImpl()
        cuenta_aggregate = repository.obtener_por_id(UUID(cuenta_id))

        if not cuenta_aggregate:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cuenta no encontrada: {cuenta_id}"
            )

        updates = (
            request.model_dump(exclude_unset=True)
            if hasattr(request, "model_dump")
            else request.dict(exclude_unset=True)
        )
        cuenta = cuenta_aggregate.cuenta
        for campo, valor in updates.items():
            if campo == "perfil" and valor is not None:
                perfil_actual = dict(cuenta.perfil or {})
                perfil_actual.update(valor)
                cuenta.perfil = perfil_actual
            else:
                setattr(cuenta, campo, valor)
        cuenta.fecha_actualizacion = datetime.now()

        repository.guardar(cuenta_aggregate)

        handler = ObtenerCuentaQueryHandler(repository)
        cuenta_data = handler.handle(ObtenerCuentaQuery(cuenta_id=UUID(cuenta_id)))
        return CuentaResponse(**cuenta_data)

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
            detail=f"Error al actualizar cuenta: {str(e)}"
        )


@router.post("/cuenta/{cuenta_id}/foto", response_model=CuentaResponse, status_code=status.HTTP_200_OK)
async def subir_foto_perfil(
    cuenta_id: str,
    request: Request,
    file: UploadFile = File(...),
    usuario: dict = Depends(obtener_usuario_actual)
):
    """
    Sube una imagen de perfil para la cuenta autenticada y actualiza foto_url.
    """
    try:
        _validar_misma_cuenta(cuenta_id, usuario)

        original_name = file.filename or ""
        extension = FilePath(original_name).suffix.lower()
        if extension not in ALLOWED_PROFILE_PHOTO_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formato de imagen no soportado. Usa JPG, PNG, WEBP o GIF"
            )

        content = await file.read()
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La imagen está vacía"
            )
        if len(content) > MAX_PROFILE_PHOTO_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La imagen supera el limite de 3 MB"
            )
        if not _looks_like_image(content, extension):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo no parece ser una imagen válida"
            )

        repository = CuentaRepositoryImpl()
        cuenta_aggregate = repository.obtener_por_id(UUID(cuenta_id))
        if not cuenta_aggregate:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cuenta no encontrada: {cuenta_id}"
            )

        PROFILE_PHOTO_DIR.mkdir(parents=True, exist_ok=True)
        file_name = f"{cuenta_id}-{uuid4().hex}{extension}"
        file_path = PROFILE_PHOTO_DIR / file_name
        file_path.write_bytes(content)

        public_url = str(request.base_url).rstrip("/") + f"/uploads/profile_photos/{file_name}"
        foto_anterior = cuenta_aggregate.cuenta.foto_url
        cuenta_aggregate.cuenta.foto_url = public_url
        cuenta_aggregate.cuenta.fecha_actualizacion = datetime.now()
        try:
            repository.guardar(cuenta_aggregate)
        except Exception:
            file_path.unlink(missing_ok=True)
            raise
        _eliminar_foto_local(foto_anterior, cuenta_id)

        handler = ObtenerCuentaQueryHandler(repository)
        cuenta_data = handler.handle(ObtenerCuentaQuery(cuenta_id=UUID(cuenta_id)))
        return CuentaResponse(**cuenta_data)

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
            detail=f"Error al subir foto: {str(e)}"
        )


@router.get("/cuenta/email/{email}", response_model=CuentaResponse, status_code=status.HTTP_200_OK)
async def obtener_cuenta_por_email(
    email: str,
    usuario: dict = Depends(obtener_usuario_actual),
):
    """
    Obtiene la información de una cuenta por email.
    
    - **email**: Email del usuario
    """
    try:
        repository = CuentaRepositoryImpl()
        handler = ObtenerCuentaPorEmailQueryHandler(repository)
        
        query = ObtenerCuentaPorEmailQuery(email=email)
        cuenta_data = handler.handle(query)
        
        if not cuenta_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cuenta no encontrada para el email: {email}"
            )

        _validar_acceso_lectura_cuenta(cuenta_data, usuario)
        return CuentaResponse(**_aplicar_privacidad_email(cuenta_data, usuario))
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al obtener cuenta: {str(e)}"
        )





@router.post("/verificar-token", response_model=TokenVerificationResponse, status_code=status.HTTP_200_OK)
async def verificar_token_endpoint(request: RefreshTokenRequest):
    """
    Verifica si un token JWT es válido.
    
    - **refresh_token**: Token a verificar (puede ser access_token o refresh_token)
    """
    try:
        repository = CuentaRepositoryImpl()
        handler = VerificarTokenQueryHandler(repository)
        
        query = VerificarTokenQuery(token=request.refresh_token)
        resultado = handler.handle(query)
        
        if not resultado:
            return TokenVerificationResponse(valido=False)
        
        return TokenVerificationResponse(**resultado)
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al verificar token: {str(e)}"
        )
