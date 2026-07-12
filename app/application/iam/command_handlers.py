from dataclasses import dataclass
from typing import Any, Dict, Optional
from uuid import UUID

from app.domain.common import Command, CommandHandler
from app.domain.iam.entities import (
    CuentaAggregate, Cuenta, RolEnum, EstadoCuentaEnum
)
from app.domain.iam.repositories import CuentaRepository
from app.infrastructure.iam.security import TokenManager, PasswordManager


@dataclass
class CrearCuentaCommand(Command):
    """Comando para crear una nueva cuenta"""
    nombre_completo: str
    email: str
    password: str
    carrera: Optional[str] = None
    telefono: Optional[str] = None
    ciudad: Optional[str] = None
    rol: str = "postulante"


class CrearCuentaHandler(CommandHandler):
    """Manejador del comando para crear una cuenta"""
    
    def __init__(self, cuenta_repository: CuentaRepository):
        self.cuenta_repository = cuenta_repository
    
    def handle(self, command: CrearCuentaCommand) -> Dict[str, Any]:
        """Maneja el comando de creación de cuenta"""
        
        email = command.email.strip().lower()

        # Validar que el email no exista
        if self.cuenta_repository.verificar_email_existe(email):
            raise ValueError("El email ya está registrado")
        
        # Validar que la contraseña sea fuerte
        if not PasswordManager.es_password_fuerte(command.password):
            raise ValueError(
                "La contraseña debe tener al menos 8 caracteres, una mayúscula, "
                "una minúscula, un número y un carácter especial"
            )
        
        # Hashear contraseña
        hash_password = PasswordManager.hashear_password(command.password)
        
        # Mapear rol string a enum
        rol_enum = RolEnum[command.rol.upper()]
        
        # Crear entidad Cuenta
        cuenta = Cuenta(
            rol=rol_enum,
            estado=EstadoCuentaEnum.ACTIVA
        )
        
        # Crear agregado
        cuenta_aggregate = CuentaAggregate(cuenta=cuenta)
        
        # Aplicar creación con las credenciales
        cuenta_aggregate.aplicar_creacion_cuenta(
            email=email,
            hash_password=hash_password,
            nombre_completo=command.nombre_completo,
            carrera=command.carrera,
            telefono=command.telefono,
            ciudad=command.ciudad,
            rol=rol_enum
        )
        
        # Guardar en repositorio
        cuenta_id = self.cuenta_repository.guardar(cuenta_aggregate)
        
        # Retornar respuesta
        return {
            "cuenta_id": str(cuenta_id),
            "nombre_completo": command.nombre_completo,
            "email": email,
            "carrera": command.carrera,
            "telefono": command.telefono,
            "ciudad": command.ciudad,
            "rol": command.rol
        }


@dataclass
class GenerarTokenCommand(Command):
    """Comando para generar un token de acceso"""
    cuenta_id: UUID
    tipo_token: str = "access"


class GenerarTokenHandler(CommandHandler):
    """Manejador del comando para generar un token"""
    
    def __init__(self, cuenta_repository: CuentaRepository):
        self.cuenta_repository = cuenta_repository
    
    def handle(self, command: GenerarTokenCommand) -> Dict[str, Any]:
        """Maneja el comando de generacion de token."""
        if command.tipo_token not in {"access", "refresh"}:
            raise ValueError("Tipo de token no permitido")

        # Recuperar la cuenta
        cuenta_aggregate = self.cuenta_repository.obtener_por_id(command.cuenta_id)
        
        if not cuenta_aggregate:
            raise ValueError(f"Cuenta no encontrada: {command.cuenta_id}")
        
        if (
            not cuenta_aggregate.cuenta.credencial.activa
            or cuenta_aggregate.cuenta.estado in {
                EstadoCuentaEnum.INACTIVA,
                EstadoCuentaEnum.SUSPENDIDA,
            }
        ):
            raise ValueError("La cuenta no esta habilitada")
        
        # Generar token
        if command.tipo_token == "refresh":
            token_value = TokenManager.crear_refresh_token({
                "sub": str(command.cuenta_id),
                "email": cuenta_aggregate.cuenta.credencial.email,
                "tipo": "refresh"
            })
        else:
            token_value = TokenManager.crear_access_token({
                "sub": str(command.cuenta_id),
                "email": cuenta_aggregate.cuenta.credencial.email,
                "rol": cuenta_aggregate.cuenta.rol.value,
                "tipo": "access"
            })
        
        # Aplicar generación de token
        cuenta_aggregate.aplicar_generacion_token(
            token_value=token_value,
            tipo_token=command.tipo_token,
            minutos_expiracion=30 if command.tipo_token == "access" else 60*24*7
        )
        
        # Guardar cambios
        self.cuenta_repository.guardar(cuenta_aggregate)
        
        return {
            "token": token_value,
            "tipo": command.tipo_token,
            "cuenta_id": str(command.cuenta_id),
            "email": cuenta_aggregate.cuenta.credencial.email
        }


@dataclass
class LoginCommand(Command):
    """Comando para login de un usuario"""
    email: str
    password: str


class LoginHandler(CommandHandler):
    """Manejador del comando para login"""
    
    def __init__(self, cuenta_repository: CuentaRepository):
        self.cuenta_repository = cuenta_repository
    
    def handle(self, command: LoginCommand) -> Dict[str, Any]:
        """Maneja el comando de login"""
        email = command.email.strip().lower()

        # Recuperar la cuenta por email
        cuenta_aggregate = self.cuenta_repository.obtener_por_email(email)
        
        if not cuenta_aggregate:
            raise ValueError("Email o contraseña incorrectos")

        if not cuenta_aggregate.cuenta.credencial.activa:
            raise ValueError("La cuenta esta inactiva")
        
        # Verificar contraseña
        if not PasswordManager.verificar_password(
            command.password,
            cuenta_aggregate.cuenta.credencial.hash_password
        ):
            # Registrar intento fallido
            cuenta_aggregate.aplicar_intento_fallido()
            self.cuenta_repository.guardar(cuenta_aggregate)
            raise ValueError("Email o contraseña incorrectos")
        
        # Verificar estado de la cuenta
        if cuenta_aggregate.cuenta.estado == EstadoCuentaEnum.SUSPENDIDA:
            raise ValueError("La cuenta está suspendida")
        
        if cuenta_aggregate.cuenta.estado == EstadoCuentaEnum.INACTIVA:
            raise ValueError("La cuenta está inactiva")
        
        # Aplicar login exitoso
        cuenta_aggregate.aplicar_login_exitoso()
        
        # Generar tokens
        access_token = TokenManager.crear_access_token({
            "sub": str(cuenta_aggregate.cuenta.cuenta_id),
            "email": cuenta_aggregate.cuenta.credencial.email,
            "rol": cuenta_aggregate.cuenta.rol.value,
            "tipo": "access"
        })
        
        refresh_token = TokenManager.crear_refresh_token({
            "sub": str(cuenta_aggregate.cuenta.cuenta_id),
            "email": cuenta_aggregate.cuenta.credencial.email,
            "tipo": "refresh"
        })
        
        # Aplicar generación de tokens
        cuenta_aggregate.aplicar_generacion_token(
            token_value=access_token,
            tipo_token="access",
            minutos_expiracion=30
        )
        
        cuenta_aggregate.aplicar_generacion_token(
            token_value=refresh_token,
            tipo_token="refresh",
            minutos_expiracion=60*24*7
        )
        
        # Guardar cambios
        self.cuenta_repository.guardar(cuenta_aggregate)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "cuenta_id": str(cuenta_aggregate.cuenta.cuenta_id),
            "email": cuenta_aggregate.cuenta.credencial.email,
            "rol": cuenta_aggregate.cuenta.rol.value
        }


@dataclass
class CambiarPasswordCommand(Command):
    """Comando para cambiar la contraseña"""
    cuenta_id: UUID
    password_actual: str
    password_nuevo: str


class CambiarPasswordHandler(CommandHandler):
    """Manejador del comando para cambiar contraseña"""
    
    def __init__(self, cuenta_repository: CuentaRepository):
        self.cuenta_repository = cuenta_repository
    
    def handle(self, command: CambiarPasswordCommand) -> bool:
        """Maneja el comando de cambio de contraseña"""
        
        # Recuperar la cuenta
        cuenta_aggregate = self.cuenta_repository.obtener_por_id(command.cuenta_id)
        
        if not cuenta_aggregate:
            raise ValueError(f"Cuenta no encontrada: {command.cuenta_id}")
        
        # Verificar contraseña actual
        if not PasswordManager.verificar_password(
            command.password_actual,
            cuenta_aggregate.cuenta.credencial.hash_password
        ):
            raise ValueError("La contraseña actual es incorrecta")
        
        # Validar que la nueva contraseña sea fuerte
        if not PasswordManager.es_password_fuerte(command.password_nuevo):
            raise ValueError(
                "La contraseña debe tener al menos 8 caracteres, una mayúscula, "
                "una minúscula, un número y un carácter especial"
            )
        
        # Hashear nueva contraseña
        nuevo_hash = PasswordManager.hashear_password(command.password_nuevo)
        
        # Aplicar cambio de contraseña
        cuenta_aggregate.aplicar_cambio_password(nuevo_hash)
        
        # Guardar cambios
        self.cuenta_repository.guardar(cuenta_aggregate)
        self.cuenta_repository.revocar_tokens(command.cuenta_id)
        
        return True
