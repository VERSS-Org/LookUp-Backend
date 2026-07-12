from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from uuid import uuid4
from jose import jwt, JWTError
import bcrypt

from app.config import settings

MAX_PASSWORD_BYTES = 72


def _ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


class TokenManager:
    """Gestor de tokens JWT"""
    
    @staticmethod
    def crear_access_token(
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Crea un token de acceso"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = _ahora_utc() + expires_delta
        else:
            expire = _ahora_utc() + timedelta(
                minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
            )
        
        to_encode.update({
            "exp": expire,
            "iat": _ahora_utc(),
            "jti": str(uuid4()),
        })
        
        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        
        return encoded_jwt
    
    @staticmethod
    def crear_refresh_token(
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Crea un token de refresco"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = _ahora_utc() + expires_delta
        else:
            # Los refresh tokens duran 7 días
            expire = _ahora_utc() + timedelta(days=7)
        
        to_encode.update({
            "exp": expire,
            "iat": _ahora_utc(),
            "jti": str(uuid4()),
        })
        
        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        
        return encoded_jwt
    
    @staticmethod
    def verificar_token(token: str) -> Optional[Dict[str, Any]]:
        """Verifica y decodifica un token"""
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
            return payload
        except JWTError:
            return None
        except Exception:
            return None
    
    @staticmethod
    def crear_token_verificacion_email(email: str) -> str:
        """Crea un token temporal para verificación de email"""
        data = {
            "email": email,
            "tipo": "email_verification"
        }
        
        to_encode = data.copy()
        expire = _ahora_utc() + timedelta(hours=24)
        to_encode.update({
            "exp": expire,
            "iat": _ahora_utc(),
            "jti": str(uuid4()),
        })
        
        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        
        return encoded_jwt


class PasswordManager:
    """Gestor de contraseñas"""
    
    @staticmethod
    def hashear_password(password: str) -> str:
        """Genera el hash de una contraseña usando bcrypt"""
        # Ensure password is a string
        if not isinstance(password, str):
            password = str(password)
        
        # Ensure password is not already hashed (bcrypt hashes start with $2b$ or $2y$)
        if password.startswith('$2b$') or password.startswith('$2y$') or password.startswith('$2a$'):
            raise ValueError("Password appears to be already hashed")
        
        # bcrypt solo procesa 72 bytes. Rechazar evita contrasenas distintas
        # que compartan el mismo prefijo efectivo.
        password_bytes = password.encode('utf-8')
        if len(password_bytes) > MAX_PASSWORD_BYTES:
            raise ValueError("La contrasena no puede superar 72 bytes")
        
        # Hash using bcrypt with rounds=12
        salt = bcrypt.gensalt(rounds=12)
        hash_password = bcrypt.hashpw(password_bytes, salt)
        
        # Return as string
        return hash_password.decode('utf-8')
    
    @staticmethod
    def verificar_password(password: str, hash_password: str) -> bool:
        """Verifica una contraseña contra su hash"""
        if not isinstance(password, str):
            password = str(password)
        
        if not isinstance(hash_password, str):
            hash_password = str(hash_password)
        
        # Encode password to bytes
        password_bytes = password.encode('utf-8')
        
        # Nunca truncar: bcrypt ignoraria el sufijo y dos contrasenas largas
        # distintas podrian autenticarse contra el mismo hash.
        if len(password_bytes) > MAX_PASSWORD_BYTES:
            return False
        
        # Encode hash_password to bytes if needed
        hash_bytes = hash_password.encode('utf-8') if isinstance(hash_password, str) else hash_password
        
        try:
            return bcrypt.checkpw(password_bytes, hash_bytes)
        except (TypeError, ValueError):
            return False
    
    @staticmethod
    def es_password_fuerte(password: str) -> bool:
        """Verifica si una contraseña cumple requisitos mínimos de seguridad"""
        if (
            not isinstance(password, str)
            or len(password.encode("utf-8")) > MAX_PASSWORD_BYTES
        ):
            return False

        # Mínimo 8 caracteres
        if len(password) < 8:
            return False
        
        # Al menos una mayúscula
        if not any(c.isupper() for c in password):
            return False
        
        # Al menos una minúscula
        if not any(c.islower() for c in password):
            return False
        
        # Al menos un número
        if not any(c.isdigit() for c in password):
            return False
        
        # Al menos un carácter especial
        caracteres_especiales = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        if not any(c in caracteres_especiales for c in password):
            return False
        
        return True
