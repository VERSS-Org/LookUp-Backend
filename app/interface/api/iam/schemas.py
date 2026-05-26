from typing import Optional, Dict, Any
from pydantic import BaseModel, EmailStr
from datetime import datetime


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
    password: str
    carrera: Optional[str] = None
    telefono: Optional[str] = None
    ciudad: Optional[str] = None
    rol: str = "postulante"


class LoginRequest(BaseModel):
    """Solicitud para login"""
    email: EmailStr
    password: str


class VerificarCuentaRequest(BaseModel):
    """Solicitud para verificar cuenta"""
    cuenta_id: str
    codigo_verificacion: str


class RefreshTokenRequest(BaseModel):
    """Solicitud para refrescar token"""
    refresh_token: str


class CambiarPasswordRequest(BaseModel):
    """Solicitud para cambiar contraseña"""
    password_actual: str
    password_nuevo: str


class CuentaUpdateRequest(BaseModel):
    """Solicitud para actualizar datos editables de una cuenta"""
    nombre_completo: Optional[str] = None
    carrera: Optional[str] = None
    telefono: Optional[str] = None
    ciudad: Optional[str] = None
    foto_url: Optional[str] = None


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
    rol: str
    estado: str
    fecha_creacion: datetime
    fecha_actualizacion: Optional[datetime] = None
    fecha_primer_acceso: Optional[datetime] = None


class VerificacionResponse(BaseModel):
    """Respuesta de verificación"""
    mensaje: str
    cuenta_id: str
    estado: str


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
