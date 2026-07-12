from sqlalchemy import Boolean, Column, String, DateTime, ForeignKey, Text, Enum as SQLAEnum
from sqlalchemy.orm import relationship
from uuid import uuid4

from app.infrastructure.database.connection import Base
from app.domain.contacto.entities import TipoFeedbackEnum, TipoMensajeEnum


class ContactoPostulacionModel(Base):
    """Modelo de la tabla de contactos de postulación"""
    __tablename__ = "contactos_postulacion"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    postulacion_id = Column(String(36), nullable=False)
    empresa_id = Column(String(36), nullable=False)
    cuenta_id = Column(String(36), nullable=False)
    tipo_mensaje = Column(SQLAEnum(TipoMensajeEnum, native_enum=False), nullable=False)
    remitente_rol = Column(String(20), nullable=False, default="empresa")
    motivo_rechazo = Column(String(500), nullable=True)
    fecha_hora = Column(DateTime, nullable=False)
    # Marca si el destinatario ya leyo el mensaje (para badges de no leidos).
    leido = Column(Boolean, nullable=False, default=False)
    
    # Relaciones
    feedbacks = relationship("FeedbackModel", back_populates="contacto", cascade="all, delete-orphan")


class FeedbackModel(Base):
    """Modelo de la tabla de feedbacks"""
    __tablename__ = "feedbacks"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    contacto_id = Column(String(36), ForeignKey("contactos_postulacion.id"), nullable=False)
    tipo = Column(SQLAEnum(TipoFeedbackEnum, native_enum=False), nullable=False)
    mensaje_texto = Column(Text, nullable=False)
    motivo_rechazo = Column(String(500), nullable=True)
    
    # Relaciones
    contacto = relationship("ContactoPostulacionModel", back_populates="feedbacks")
