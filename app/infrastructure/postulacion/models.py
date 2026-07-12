from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Enum as SQLAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from app.infrastructure.database.connection import Base
from app.domain.postulacion.entities import EstadoPostulacionEnum

class PostulacionModel(Base):
    """Modelo simplificado de la tabla de postulaciones"""
    __tablename__ = "postulaciones"
    __table_args__ = (
        UniqueConstraint(
            "cuenta_id", "puesto_id", name="uq_postulacion_cuenta_puesto"
        ),
    )
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    postulacion_id = Column(String(36), nullable=False, unique=True)
    cuenta_id = Column(String(36), nullable=False)  # UUID de la cuenta
    puesto_id = Column(String(36), nullable=False)  # UUID string del puesto (antes Integer)
    fecha_postulacion = Column(DateTime, nullable=False)
    estado = Column(SQLAEnum(EstadoPostulacionEnum, native_enum=False), nullable=False)
    documentos_adjuntos = Column(JSON, nullable=False, default=list)
    resultado = Column(String(100), nullable=True)
    
    # Relaciones
    hitos = relationship("HitoModel", back_populates="postulacion", cascade="all, delete-orphan")


class HitoModel(Base):
    """Modelo simplificado de hitos"""
    __tablename__ = "hitos"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    postulacion_id = Column(Integer, ForeignKey("postulaciones.id"), nullable=False)
    fecha = Column(DateTime, nullable=False)
    descripcion = Column(Text, nullable=False)
    
    # Relaciones
    postulacion = relationship("PostulacionModel", back_populates="hitos")
