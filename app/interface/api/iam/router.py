from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from typing import Optional
from datetime import datetime
from pathlib import Path as FilePath
from uuid import UUID
from uuid import uuid4

from app.application.iam.command_handlers import (
    CrearCuentaHandler, CrearCuentaCommand,
    LoginHandler, LoginCommand,
    GenerarTokenHandler, GenerarTokenCommand,
    VerificarCuentaHandler, VerificarCuentaCommand,
    CambiarPasswordHandler, CambiarPasswordCommand
)
from app.application.iam.query_handlers import (
    ObtenerCuentaQueryHandler, ObtenerCuentaQuery,
    ObtenerCuentaPorEmailQueryHandler, ObtenerCuentaPorEmailQuery,
    VerificarTokenQueryHandler, VerificarTokenQuery
)
from app.infrastructure.iam.repositories import CuentaRepositoryImpl
from app.infrastructure.iam.security import TokenManager
from app.interface.api.dependencies import obtener_usuario_actual

from .schemas import (
    CrearCuentaRequest, LoginRequest, VerificarCuentaRequest,
    RefreshTokenRequest, CambiarPasswordRequest, CuentaUpdateRequest,
    TokenResponse, CuentaResponse, VerificacionResponse,
    MensajeResponse, TokenVerificationResponse
)

router = APIRouter(prefix="/iam", tags=["IAM"])
PROFILE_PHOTO_DIR = FilePath("uploads/profile_photos")
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


@router.post("/registrar", response_model=CuentaResponse, status_code=status.HTTP_201_CREATED)
async def registrar_cuenta(request: CrearCuentaRequest):
    """
    Registra una nueva cuenta de usuario.
    - **email**: Email único del usuario
    - **password**: Contraseña (mín. 8 caracteres, mayúscula, minúscula, número, carácter especial)
    - **tipo_cuenta**: Tipo de cuenta (candidato, empresa, admin) - por defecto 'candidato'
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


@router.post("/verificar-cuenta", response_model=VerificacionResponse, status_code=status.HTTP_200_OK)
async def verificar_cuenta(request: VerificarCuentaRequest):
    """
    Verifica una cuenta usando el código de verificación enviado al email.
    
    - **cuenta_id**: ID de la cuenta a verificar
    - **codigo_verificacion**: Código enviado al email del usuario
    """
    try:
        repository = CuentaRepositoryImpl()
        handler = VerificarCuentaHandler(repository)
        
        command = VerificarCuentaCommand(
            cuenta_id=UUID(request.cuenta_id),
            codigo_verificacion=request.codigo_verificacion
        )
        
        handler.handle(command)
        
        # Obtener cuenta actualizada
        query_handler = ObtenerCuentaQueryHandler(repository)
        query = ObtenerCuentaQuery(cuenta_id=UUID(request.cuenta_id))
        cuenta_data = query_handler.handle(query)
        
        return VerificacionResponse(
            mensaje="Cuenta verificada exitosamente",
            cuenta_id=cuenta_data['cuenta_id'],
            estado=cuenta_data['estado']
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al verificar cuenta: {str(e)}"
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
        
        # Obtener la cuenta
        repository = CuentaRepositoryImpl()
        query_handler = ObtenerCuentaQueryHandler(repository)
        query = ObtenerCuentaQuery(cuenta_id=UUID(payload.get("sub")))
        cuenta_data = query_handler.handle(query)
        
        if not cuenta_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cuenta no encontrada"
            )
        
        # Generar nuevo access token
        nuevo_access_token = TokenManager.crear_access_token({
            "sub": payload.get("sub"),
            "email": payload.get("email"),
            "rol": cuenta_data.get("rol"),
            "tipo": "access"
        })
        
        return TokenResponse(
            access_token=nuevo_access_token,
            token_type="bearer",
            cuenta_id=payload.get("sub"),
            email=payload.get("email"),
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
async def obtener_cuenta(cuenta_id: str):
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
        
        return CuentaResponse(**cuenta_data)
    
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
                detail="La imagen esta vacia"
            )
        if len(content) > MAX_PROFILE_PHOTO_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La imagen supera el limite de 3 MB"
            )
        if not _looks_like_image(content, extension):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo no parece ser una imagen valida"
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
        cuenta_aggregate.cuenta.foto_url = public_url
        cuenta_aggregate.cuenta.fecha_actualizacion = datetime.now()
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
            detail=f"Error al subir foto: {str(e)}"
        )


@router.get("/cuenta/email/{email}", response_model=CuentaResponse, status_code=status.HTTP_200_OK)
async def obtener_cuenta_por_email(email: str):
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
        
        return CuentaResponse(**cuenta_data)
    
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
