from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from datetime import datetime

from app.infrastructure.database.connection import Base


class PuestoModel(Base):
    """Modelo de la tabla de puestos"""
    __tablename__ = "puestos"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    titulo = Column(String(300), nullable=False)
    empresa = Column(String(300), nullable=False)
    descripcion = Column(String(5000), nullable=False)
    ubicacion = Column(String(300), nullable=True)
    salario_min = Column(Float, nullable=True)
    salario_max = Column(Float, nullable=True)
    moneda = Column(String(10), nullable=False, default="PEN")
    tipo_contrato = Column(String(50), nullable=False, default="tiempo_completo")
    fecha_publicacion = Column(DateTime, nullable=False, default=datetime.now)
    fecha_cierre = Column(DateTime, nullable=True)
    estado = Column(String(50), nullable=False, default="abierto")
    requisitos = relationship(
        "RequisitoPuestoModel",
        back_populates="puesto",
        cascade="all, delete-orphan",
        order_by="RequisitoPuestoModel.id",
    )


class RequisitoPuestoModel(Base):
    """Requisito persistido de una oferta de trabajo."""

    __tablename__ = "requisitos_puesto"

    id = Column(Integer, primary_key=True, autoincrement=True)
    puesto_id = Column(
        Integer,
        ForeignKey("puestos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tipo = Column(String(100), nullable=False, default="general")
    descripcion = Column(String(1000), nullable=False)
    es_obligatorio = Column(Boolean, nullable=False, default=True)

    puesto = relationship("PuestoModel", back_populates="requisitos")


class PuestoMapeo(Base):
    """Tabla auxiliar para mapear UUIDs de dominio a IDs de BD"""
    __tablename__ = "puesto_mapeo"
    
    uuid_id = Column(String(36), primary_key=True)
    bd_id = Column(
        Integer,
        ForeignKey("puestos.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
