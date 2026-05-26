import json
from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session

from sqlalchemy.exc import IntegrityError

from app.domain.iam.entities import (
    CuentaAggregate, Cuenta, Credencial, Token, RolEnum, EstadoCuentaEnum
)
from app.domain.iam.repositories import CuentaRepository
from app.infrastructure.iam.models import CuentaModel, TokenModel, HistorialAccesoModel
from app.infrastructure.database.connection import SessionLocal


class CuentaRepositoryImpl(CuentaRepository):
    """Implementación del repositorio de cuentas usando SQLAlchemy"""
    
    def __init__(self, session: Optional[Session] = None):
        self.session = session or SessionLocal()
    
    def guardar(self, cuenta_aggregate: CuentaAggregate) -> UUID:
        """Guarda o actualiza una cuenta"""
        try:
            cuenta = cuenta_aggregate.cuenta
            
            # Buscar si existe
            cuenta_existente = self.session.query(CuentaModel).filter_by(
                id=str(cuenta.cuenta_id)
            ).first()
            
            if cuenta_existente:
                # Actualizar
                cuenta_existente.email = cuenta.credencial.email
                cuenta_existente.hash_password = cuenta.credencial.hash_password
                cuenta_existente.nombre_completo = cuenta.nombre_completo
                cuenta_existente.carrera = cuenta.carrera
                cuenta_existente.telefono = cuenta.telefono
                cuenta_existente.ciudad = cuenta.ciudad
                cuenta_existente.foto_url = cuenta.foto_url
                cuenta_existente.rol = cuenta.rol
                cuenta_existente.estado = cuenta.estado
                cuenta_existente.fecha_actualizacion = cuenta.fecha_actualizacion
                cuenta_existente.fecha_primer_acceso = cuenta.fecha_primer_acceso
                cuenta_existente.intentos_fallidos = cuenta_aggregate.intentos_fallidos
                if cuenta.datos_verificacion:
                    cuenta_existente.datos_verificacion = json.dumps(cuenta.datos_verificacion)
            else:
                # Crear nueva
                cuenta_model = CuentaModel(
                    id=cuenta.cuenta_id,
                    nombre_completo=cuenta.nombre_completo,
                    carrera=cuenta.carrera,
                    telefono=cuenta.telefono,
                    ciudad=cuenta.ciudad,
                    foto_url=cuenta.foto_url,
                    email=cuenta.credencial.email,
                    hash_password=cuenta.credencial.hash_password,
                    rol=cuenta.rol,
                    estado=cuenta.estado,
                    datos_verificacion=json.dumps(cuenta.datos_verificacion) if cuenta.datos_verificacion else None,
                    fecha_creacion=cuenta.fecha_creacion,
                    fecha_actualizacion=cuenta.fecha_actualizacion,
                    fecha_primer_acceso=cuenta.fecha_primer_acceso,
                    intentos_fallidos=cuenta_aggregate.intentos_fallidos,
                    activa=True
                )
                self.session.add(cuenta_model)
            
            # Guardar tokens activos
            for tipo_token, token in cuenta_aggregate.tokens_activos.items():
                token_existente = self.session.query(TokenModel).filter_by(
                    id=token.id_token
                ).first()
                
                if not token_existente:
                    token_model = TokenModel(
                        id=token.id_token,
                        cuenta_id=cuenta.cuenta_id,
                        token_value=token.token_value,
                        tipo_token=token.tipo_token,
                        fecha_creacion=token.fecha_creacion,
                        fecha_expiracion=token.fecha_expiracion,
                        activo=token.activo
                    )
                    self.session.add(token_model)
            
            # Guardar historial de accesos
            for acceso in cuenta_aggregate.historial_accesos:
                historial_model = HistorialAccesoModel(
                    cuenta_id=cuenta.cuenta_id,
                    tipo_acceso=acceso['tipo_acceso'],
                    detalles=json.dumps(acceso['detalles']) if acceso.get('detalles') else None,
                    fecha_creacion=acceso['fecha']
                )
                self.session.add(historial_model)
            
            self.session.commit()
            return cuenta.cuenta_id
        
        except IntegrityError as ie:
            self.session.rollback()
            # Log the actual error to help debugging
            error_detail = str(ie.orig) if ie.orig else str(ie)
            if "email" in error_detail.lower() or "unique" in error_detail.lower():
                raise ValueError("El email ya está registrado")
            else:
                raise ValueError(f"Database integrity error: {error_detail}")
        except Exception as e:
            self.session.rollback()
            raise e
    
    def obtener_por_id(self, cuenta_id: UUID) -> Optional[CuentaAggregate]:
        """Recupera una cuenta por su ID"""
        try:
            cuenta_model = self.session.query(CuentaModel).filter_by(
                id=cuenta_id
            ).first()
            
            if not cuenta_model:
                return None
            
            return self._mapear_modelo_a_aggregate(cuenta_model)
        except Exception as e:
            raise e
    
    def obtener_por_email(self, email: str) -> Optional[CuentaAggregate]:
        """Recupera una cuenta por su email"""
        try:
            cuenta_model = self.session.query(CuentaModel).filter_by(
                email=email
            ).first()
            
            if not cuenta_model:
                return None
            
            return self._mapear_modelo_a_aggregate(cuenta_model)
        except Exception as e:
            raise e
    
    
    def verificar_email_existe(self, email: str) -> bool:
        """Verifica si un email ya está registrado"""
        try:
            cuenta = self.session.query(CuentaModel).filter_by(
                email=email
            ).first()
            return cuenta is not None
        except Exception as e:
            raise e
    
    def listar_todas(self) -> List[CuentaAggregate]:
        """Lista todas las cuentas"""
        try:
            cuentas_model = self.session.query(CuentaModel).all()
            return [self._mapear_modelo_a_aggregate(m) for m in cuentas_model]
        except Exception as e:
            raise e
    
    def _mapear_modelo_a_aggregate(self, cuenta_model: CuentaModel) -> CuentaAggregate:
        """Mapea un modelo de base de datos a un agregado"""
        # Recuperar tokens asociados
        tokens_model = self.session.query(TokenModel).filter_by(
            cuenta_id=cuenta_model.id
        ).all()
        
        tokens_dict = {}
        for token_model in tokens_model:
            if token_model.activo:
                token = Token(
                    id_token=token_model.id,
                    token_value=token_model.token_value,
                    tipo_token=token_model.tipo_token,
                    fecha_creacion=token_model.fecha_creacion,
                    fecha_expiracion=token_model.fecha_expiracion,
                    activo=token_model.activo
                )
                tokens_dict[token_model.tipo_token] = token
        
        # Recuperar historial de accesos
        historial_model = self.session.query(HistorialAccesoModel).filter_by(
            cuenta_id=cuenta_model.id
        ).all()
        
        historial = []
        for h in historial_model:
            historial.append({
                'tipo_acceso': h.tipo_acceso,
                'fecha': h.fecha_creacion.isoformat(),
                'detalles': json.loads(h.detalles) if h.detalles else {}
            })
        
        # Crear credencial
        credencial = Credencial(
            id_credencial=cuenta_model.id,
            email=cuenta_model.email,
            hash_password=cuenta_model.hash_password,
            fecha_creacion=cuenta_model.fecha_creacion,
            fecha_ultimo_acceso=cuenta_model.fecha_primer_acceso,
            activa=cuenta_model.activa
        )
        
        # Crear entidad Cuenta
        datos_verificacion = {}
        if cuenta_model.datos_verificacion:
            try:
                datos_verificacion = json.loads(cuenta_model.datos_verificacion)
            except:
                datos_verificacion = {}
        
        cuenta = Cuenta(
            cuenta_id=cuenta_model.id,
            credencial=credencial,
            nombre_completo=cuenta_model.nombre_completo,
            carrera=cuenta_model.carrera,
            telefono=cuenta_model.telefono,
            ciudad=cuenta_model.ciudad,
            foto_url=cuenta_model.foto_url,
            rol=cuenta_model.rol,
            estado=cuenta_model.estado,
            datos_verificacion=datos_verificacion,
            fecha_creacion=cuenta_model.fecha_creacion,
            fecha_actualizacion=cuenta_model.fecha_actualizacion,
            fecha_primer_acceso=cuenta_model.fecha_primer_acceso
        )
        
        # Crear agregado
        aggregate = CuentaAggregate(
            cuenta=cuenta,
            tokens_activos=tokens_dict,
            historial_accesos=historial,
            intentos_fallidos=cuenta_model.intentos_fallidos
        )
        
        return aggregate
