from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.domain.common import Query, QueryHandler
from app.domain.iam.entities import EstadoCuentaEnum
from app.domain.iam.repositories import CuentaRepository
from app.infrastructure.iam.security import TokenManager


@dataclass
class ObtenerCuentaQuery(Query):
    """Query para obtener una cuenta por ID"""
    cuenta_id: UUID


class ObtenerCuentaQueryHandler(QueryHandler):
    """Manejador de consulta para obtener una cuenta"""
    
    def __init__(self, cuenta_repository: CuentaRepository):
        self.cuenta_repository = cuenta_repository
    
    def handle(self, query: ObtenerCuentaQuery) -> Optional[Dict[str, Any]]:
        """Maneja la consulta de cuenta por ID"""
        
        cuenta_aggregate = self.cuenta_repository.obtener_por_id(query.cuenta_id)
        
        if not cuenta_aggregate:
            return None
        
        cuenta = cuenta_aggregate.cuenta
        
        return {
            'cuenta_id': str(cuenta.cuenta_id),
            'nombre_completo': cuenta.nombre_completo,
            'carrera': cuenta.carrera,
            'telefono': cuenta.telefono,
            'ciudad': cuenta.ciudad,
            "foto_url": cuenta.foto_url,
            "perfil": cuenta.perfil,
            "email": cuenta.credencial.email,
            "rol": cuenta.rol.value,
            "estado": cuenta.estado.value,
            "activa": cuenta.credencial.activa,
            "fecha_creacion": cuenta.fecha_creacion,
            "fecha_actualizacion": cuenta.fecha_actualizacion,
            "fecha_primer_acceso": cuenta.fecha_primer_acceso
        }


@dataclass
class ObtenerCuentaPorEmailQuery(Query):
    """Query para obtener una cuenta por email"""
    email: str


class ObtenerCuentaPorEmailQueryHandler(QueryHandler):
    """Manejador de consulta para obtener una cuenta por email"""
    
    def __init__(self, cuenta_repository: CuentaRepository):
        self.cuenta_repository = cuenta_repository
    
    def handle(self, query: ObtenerCuentaPorEmailQuery) -> Optional[Dict[str, Any]]:
        """Maneja la consulta de cuenta por email"""
        
        cuenta_aggregate = self.cuenta_repository.obtener_por_email(query.email)
        
        if not cuenta_aggregate:
            return None
        
        cuenta = cuenta_aggregate.cuenta
        
        return {
            "cuenta_id": str(cuenta.cuenta_id),
            "nombre_completo": cuenta.nombre_completo,
            "email": cuenta.credencial.email,
            "carrera": cuenta.carrera,
            "telefono": cuenta.telefono,
            "ciudad": cuenta.ciudad,
            "foto_url": cuenta.foto_url,
            "perfil": cuenta.perfil,
            "rol": cuenta.rol.value,
            "estado": cuenta.estado.value,
            "activa": cuenta.credencial.activa,
            "fecha_creacion": cuenta.fecha_creacion,
            "fecha_actualizacion": cuenta.fecha_actualizacion,
            "fecha_primer_acceso": cuenta.fecha_primer_acceso
        }





@dataclass
class VerificarTokenQuery(Query):
    """Query para verificar un token"""
    token: str


class VerificarTokenQueryHandler(QueryHandler):
    """Manejador de consulta para verificar un token"""
    
    def __init__(self, cuenta_repository: CuentaRepository):
        self.cuenta_repository = cuenta_repository
    
    def handle(self, query: VerificarTokenQuery) -> Optional[Dict[str, Any]]:
        """Maneja la consulta de verificación de token"""
        
        payload = TokenManager.verificar_token(query.token)
        
        if not payload:
            return None

        tipo_token = payload.get("tipo")
        if tipo_token not in {"access", "refresh"}:
            return None

        try:
            cuenta_id = UUID(payload["sub"])
        except (KeyError, TypeError, ValueError):
            return None

        cuenta = self.cuenta_repository.obtener_por_id(cuenta_id)
        if (
            not cuenta
            or not cuenta.cuenta.credencial.activa
            or cuenta.cuenta.estado in {
                EstadoCuentaEnum.INACTIVA,
                EstadoCuentaEnum.SUSPENDIDA,
            }
            or not self.cuenta_repository.token_esta_activo(
                query.token,
                cuenta_id,
                tipo_token,
            )
        ):
            return None
        
        return {
            "valido": True,
            "cuenta_id": str(cuenta_id),
            "email": cuenta.cuenta.credencial.email,
            "rol": cuenta.cuenta.rol.value,
            "tipo": tipo_token,
        }


@dataclass
class ListarCuentasQuery(Query):
    """Query para listar todas las cuentas"""
    pass


class ListarCuentasQueryHandler(QueryHandler):
    """Manejador de consulta para listar cuentas"""
    
    def __init__(self, cuenta_repository: CuentaRepository):
        self.cuenta_repository = cuenta_repository
    
    def handle(self, query: ListarCuentasQuery) -> List[Dict[str, Any]]:
        """Maneja la consulta de listado de cuentas"""
        
        cuentas_aggregate = self.cuenta_repository.listar_todas()
        
        return [
            {
                'cuenta_id': str(agg.cuenta.cuenta_id),
                'nombre_completo': agg.cuenta.nombre_completo,
                'carrera': agg.cuenta.carrera,
                'telefono': agg.cuenta.telefono,
                'ciudad': agg.cuenta.ciudad,
                "foto_url": agg.cuenta.foto_url,
                "perfil": agg.cuenta.perfil,
                "email": agg.cuenta.credencial.email,
                "rol": agg.cuenta.rol.value,
                "estado": agg.cuenta.estado.value,
                "fecha_creacion": agg.cuenta.fecha_creacion
            }
            for agg in cuentas_aggregate
        ]
