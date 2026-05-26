from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

from app.infrastructure.database.connection import Base
from app.domain.iam.entities import RolEnum, EstadoCuentaEnum


class CuentaModel(Base):
    """Modelo de base de datos para la tabla de cuentas"""
    __tablename__ = "cuentas"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=False, unique=True, index=True)
    hash_password = Column(String(255), nullable=False)
    nombre_completo = Column(String(255), nullable=False)
    carrera = Column(String(255), nullable=True)
    telefono = Column(String(50), nullable=True)
    ciudad = Column(String(100), nullable=True)
    foto_url = Column(Text, nullable=True)
    rol = Column(Enum(RolEnum), nullable=False, default=RolEnum.POSTULANTE)
    estado = Column(Enum(EstadoCuentaEnum), nullable=False, default=EstadoCuentaEnum.NO_VERIFICADA)
    datos_verificacion = Column(Text, nullable=True)  # JSON almacenado como texto
    intentos_fallidos = Column(Integer, default=0)
    fecha_creacion = Column(DateTime, nullable=False, default=datetime.now)
    fecha_actualizacion = Column(DateTime, nullable=True)
    fecha_primer_acceso = Column(DateTime, nullable=True)
    activa = Column(Boolean, default=True)
    
    def __repr__(self):
        return f"<CuentaModel(id={self.id}, email={self.email}, rol={self.rol})>"


class TokenModel(Base):
    """Modelo de base de datos para la tabla de tokens"""
    __tablename__ = "tokens"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cuenta_id = Column(UUID(as_uuid=True), ForeignKey("cuentas.id"), nullable=False)
    token_value = Column(String(500), nullable=False, unique=True)
    tipo_token = Column(String(50), nullable=False, default="access")  # access, refresh, verification
    fecha_creacion = Column(DateTime, nullable=False, default=datetime.now)
    fecha_expiracion = Column(DateTime, nullable=True)
    activo = Column(Boolean, default=True)
    
    def __repr__(self):
        return f"<TokenModel(id={self.id}, cuenta_id={self.cuenta_id}, tipo_token={self.tipo_token})>"


class HistorialAccesoModel(Base):
    """Modelo de base de datos para el historial de accesos"""
    __tablename__ = "historial_accesos"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cuenta_id = Column(UUID(as_uuid=True), ForeignKey("cuentas.id"), nullable=False)
    tipo_acceso = Column(String(100), nullable=False)
    detalles = Column(Text, nullable=True)  # JSON almacenado como texto
    fecha_creacion = Column(DateTime, nullable=False, default=datetime.now)
    
    def __repr__(self):
        return f"<HistorialAccesoModel(id={self.id}, cuenta_id={self.cuenta_id}, tipo_acceso={self.tipo_acceso})>"
