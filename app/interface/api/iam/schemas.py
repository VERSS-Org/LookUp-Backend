from typing import Optional, Dict, Any
from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import datetime

# Roles que un usuario puede elegir al registrarse. Las cuentas admin no se
# crean por auto-servicio.
ROLES_REGISTRABLES = {"postulante", "empresa"}


def _normalizar_email(value: EmailStr) -> str:
    return str(value).strip().lower()


# Esquemas de solicitud
class DatosContacto(BaseModel):
    """Datos de contacto del usuario"""
    telefono: Optional[str] = None
    ciudad: Optional[str] = None
    pais: Optional[str] = None


class CrearCuentaRequest(BaseModel):
    """Solicitud para crear una nueva cuenta"""
    nombre_completo: str
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    carrera: Optional[str] = None
    telefono: Optional[str] = None
    ciudad: Optional[str] = None
    rol: str = "postulante"

    @field_validator("nombre_completo")
    @classmethod
    def validar_nombre(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("nombre_completo no puede estar vacío")
        return value

    @field_validator("rol")
    @classmethod
    def validar_rol(cls, value: str) -> str:
        rol = value.strip().lower()
        if rol not in ROLES_REGISTRABLES:
            raise ValueError(
                f"Rol inválido. Roles permitidos: {sorted(ROLES_REGISTRABLES)}"
            )
        return rol

    @field_validator("email")
    @classmethod
    def normalizar_email(cls, value: EmailStr) -> str:
        return _normalizar_email(value)


class LoginRequest(BaseModel):
    """Solicitud para login"""
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)

    @field_validator("email")
    @classmethod
    def normalizar_email(cls, value: EmailStr) -> str:
        return _normalizar_email(value)


class RecuperarPasswordRequest(BaseModel):
    """Solicitud de codigo de recuperacion de contrasena"""
    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalizar_email(cls, value: EmailStr) -> str:
        return _normalizar_email(value)


class RestablecerPasswordRequest(BaseModel):
    """Restablece la contrasena con el codigo recibido"""
    email: EmailStr
    codigo: str
    password_nuevo: str = Field(min_length=8, max_length=72)

    @field_validator("email")
    @classmethod
    def normalizar_email(cls, value: EmailStr) -> str:
        return _normalizar_email(value)


class RecuperacionResponse(BaseModel):
    """Respuesta neutra de recuperacion (no revela si la cuenta existe)"""
    mensaje: str
    # Solo se devuelve en desarrollo cuando EXPOSE_RESET_CODE esta habilitado.
    codigo_dev: Optional[str] = None


class RefreshTokenRequest(BaseModel):
    """Solicitud para refrescar token"""
    refresh_token: str


class CambiarPasswordRequest(BaseModel):
    """Solicitud para cambiar contraseña"""
    password_actual: str = Field(min_length=1, max_length=72)
    password_nuevo: str = Field(min_length=8, max_length=72)


class CuentaUpdateRequest(BaseModel):
    """Solicitud para actualizar datos editables de una cuenta"""
    nombre_completo: Optional[str] = None
    carrera: Optional[str] = None
    telefono: Optional[str] = None
    ciudad: Optional[str] = None
    foto_url: Optional[str] = None
    perfil: Optional[Dict[str, Any]] = None

    @field_validator("nombre_completo")
    @classmethod
    def validar_nombre(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("nombre_completo no puede estar vacío")
        return value


# Esquemas de respuesta
class TokenResponse(BaseModel):
    """Respuesta con token"""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    cuenta_id: Optional[str] = None
    email: Optional[str] = None
    rol: Optional[str] = None


class CuentaResponse(BaseModel):
    """Respuesta con datos de cuenta"""
    cuenta_id: str
    nombre_completo: str
    email: str
    carrera: Optional[str] = None
    telefono: Optional[str] = None
    ciudad: Optional[str] = None
    foto_url: Optional[str] = None
    perfil: Optional[Dict[str, Any]] = None
    rol: str
    estado: str
    fecha_creacion: datetime
    fecha_actualizacion: Optional[datetime] = None
    fecha_primer_acceso: Optional[datetime] = None


class MensajeResponse(BaseModel):
    """Respuesta simple con mensaje"""
    mensaje: str
    exito: bool = True


class TokenVerificationResponse(BaseModel):
    """Respuesta de verificación de token"""
    valido: bool
    cuenta_id: Optional[str] = None
    email: Optional[str] = None
    rol: Optional[str] = None
    tipo: Optional[str] = None
