from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, Any
from uuid import UUID, uuid4

from app.domain.common import AggregateRoot


class RolEnum(str, Enum):
    """Roles disponibles en el sistema"""
    POSTULANTE = "postulante"
    EMPRESA = "empresa"


class EstadoCuentaEnum(str, Enum):
    """Estados posibles de una cuenta"""
    ACTIVA = "activa"
    INACTIVA = "inactiva"
    SUSPENDIDA = "suspendida"
    VERIFICADA = "verificada"
    NO_VERIFICADA = "no_verificada"


@dataclass(frozen=True)
class Credencial:
    """Value Object que representa las credenciales de un usuario"""
    id_credencial: UUID = field(default_factory=uuid4)
    email: str = ""
    hash_password: str = ""
    fecha_creacion: datetime = field(default_factory=datetime.now)
    fecha_ultimo_acceso: Optional[datetime] = None
    activa: bool = True
    
    def validar_credencial(self) -> bool:
        """Valida que la credencial tenga email y contraseña válidos"""
        return (self.email and "@" in self.email and 
                self.hash_password and len(self.hash_password) > 20)


@dataclass(frozen=True)
class Token:
    """Value Object que representa un token de acceso"""
    id_token: UUID = field(default_factory=uuid4)
    token_value: str = ""
    tipo_token: str = "access"  # access, refresh, verification
    fecha_creacion: datetime = field(default_factory=datetime.now)
    fecha_expiracion: Optional[datetime] = None
    activo: bool = True
    
    def esta_expirado(self) -> bool:
        """Verifica si el token ha expirado"""
        if self.fecha_expiracion is None:
            return False
        return datetime.now() > self.fecha_expiracion
    
    def es_valido(self) -> bool:
        """Verifica si el token es válido (activo y no expirado)"""
        return self.activo and not self.esta_expirado()


@dataclass
class Cuenta:
    """Entity que representa la cuenta de un usuario"""
    cuenta_id: UUID = field(default_factory=uuid4)
    credencial: Credencial = field(default_factory=Credencial)
    nombre_completo: str = ""
    carrera: Optional[str] = None
    telefono: Optional[str] = None
    ciudad: Optional[str] = None
    foto_url: Optional[str] = None
    # Perfil extendido (descripcion, experiencia, educacion, certificados,
    # habilidades, idiomas, extras) almacenado como dict JSON.
    perfil: Optional[dict] = None
    rol: RolEnum = RolEnum.POSTULANTE
    estado: EstadoCuentaEnum = EstadoCuentaEnum.NO_VERIFICADA
    fecha_creacion: datetime = field(default_factory=datetime.now)
    fecha_actualizacion: Optional[datetime] = None
    fecha_primer_acceso: Optional[datetime] = None
    
    def cambiar_estado(self, nuevo_estado: EstadoCuentaEnum) -> None:
        """Cambia el estado de la cuenta"""
        self.estado = nuevo_estado
        self.fecha_actualizacion = datetime.now()
    
    def registrar_primer_acceso(self) -> None:
        """Registra el primer acceso a la cuenta"""
        if self.fecha_primer_acceso is None:
            self.fecha_primer_acceso = datetime.now()
            self.fecha_actualizacion = datetime.now()


@dataclass
class CuentaAggregate(AggregateRoot):
    """
    Aggregate que sirve como raíz de consistencia para la gestión de cuentas IAM
    """
    cuenta: Cuenta
    tokens_activos: Dict[str, Token] = field(default_factory=dict)
    historial_accesos: list = field(default_factory=list)
    intentos_fallidos: int = 0
    
    def aplicar_creacion_cuenta(
        self,
        email: str,
        hash_password: str,
        nombre_completo: str = "",
        carrera: Optional[str] = None,
        telefono: Optional[str] = None,
        ciudad: Optional[str] = None,
        foto_url: Optional[str] = None,
        rol: RolEnum = RolEnum.POSTULANTE
    ) -> None:
        """Aplica la creación de una nueva cuenta"""
        credencial = Credencial(
            email=email,
            hash_password=hash_password
        )
        
        self.cuenta.credencial = credencial
        self.cuenta.nombre_completo = nombre_completo
        self.cuenta.carrera = carrera
        self.cuenta.telefono = telefono
        self.cuenta.ciudad = ciudad
        self.cuenta.foto_url = foto_url
        self.cuenta.rol = rol
        
        self.add_event(CuentaCreada(
            self.cuenta.cuenta_id,
            email,
            rol=rol
        ))
    
    def aplicar_generacion_token(
        self,
        token_value: str,
        tipo_token: str = "access",
        minutos_expiracion: int = 30
    ) -> None:
        """Aplica la generación de un nuevo token"""
        fecha_expiracion = datetime.now() + timedelta(minutes=minutos_expiracion)
        
        token = Token(
            token_value=token_value,
            tipo_token=tipo_token,
            fecha_expiracion=fecha_expiracion
        )
        
        # Almacenar token activo (mantener último token)
        self.tokens_activos[tipo_token] = token
        
        # Registrar acceso
        self._registrar_acceso("token_generado", {
            "tipo_token": tipo_token,
            "fecha_expiracion": fecha_expiracion.isoformat()
        })
        
        self.add_event(TokenGenerado(
            self.cuenta.cuenta_id,
            token.id_token,
            tipo_token
        ))
    
    def aplicar_login_exitoso(self) -> None:
        """Aplica un login exitoso"""
        self.cuenta.registrar_primer_acceso()
        self.intentos_fallidos = 0
        
        self._registrar_acceso("login_exitoso", {
            "fecha": datetime.now().isoformat()
        })
        
        self.add_event(LoginExitoso(
            self.cuenta.cuenta_id
        ))
    
    def aplicar_intento_fallido(self) -> None:
        """Registra un intento de acceso fallido"""
        self.intentos_fallidos += 1
        
        self._registrar_acceso("intento_fallido", {
            "numero_intento": self.intentos_fallidos,
            "fecha": datetime.now().isoformat()
        })
        
        # Suspender cuenta después de 5 intentos fallidos
        if self.intentos_fallidos >= 5:
            self.cuenta.cambiar_estado(EstadoCuentaEnum.SUSPENDIDA)
            self.add_event(CuentaSuspendida(
                self.cuenta.cuenta_id,
                "Demasiados intentos fallidos"
            ))
    
    def aplicar_cambio_password(self, nuevo_hash_password: str) -> None:
        """Aplica el cambio de contraseña"""
        credencial_nueva = Credencial(
            id_credencial=self.cuenta.credencial.id_credencial,
            email=self.cuenta.credencial.email,
            hash_password=nuevo_hash_password,
            fecha_creacion=self.cuenta.credencial.fecha_creacion,
            activa=True
        )
        
        self.cuenta.credencial = credencial_nueva
        self.cuenta.fecha_actualizacion = datetime.now()
        
        # Limpiar tokens activos al cambiar contraseña
        self.tokens_activos.clear()
        
        self._registrar_acceso("cambio_password", {
            "fecha": datetime.now().isoformat()
        })
        
        self.add_event(PasswordActualizado(
            self.cuenta.cuenta_id
        ))
    
    def _registrar_acceso(self, tipo_acceso: str, detalles: Dict[str, Any]) -> None:
        """Registra un acceso o evento en el historial"""
        self.historial_accesos.append({
            "tipo_acceso": tipo_acceso,
            "fecha": datetime.now(),
            "detalles": detalles
        })


# Eventos de dominio
@dataclass
class CuentaCreada:
    """Evento que se emite cuando se crea una nueva cuenta"""
    cuenta_id: UUID
    email: str
    rol: RolEnum


@dataclass
class TokenGenerado:
    """Evento que se emite cuando se genera un token"""
    cuenta_id: UUID
    token_id: UUID
    tipo_token: str


@dataclass
class LoginExitoso:
    """Evento que se emite cuando hay un login exitoso"""
    cuenta_id: UUID


@dataclass
class CuentaSuspendida:
    """Evento que se emite cuando se suspende una cuenta"""
    cuenta_id: UUID
    razon: str


@dataclass
class PasswordActualizado:
    """Evento que se emite cuando se actualiza la contraseña"""
    cuenta_id: UUID
