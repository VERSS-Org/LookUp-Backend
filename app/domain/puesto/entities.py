from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4

from app.domain.common import AggregateRoot


class EstadoPuestoEnum(str, Enum):
    """Valores posibles para el estado de un puesto"""
    ABIERTO = "abierto"
    CERRADO = "cerrado"


class TipoContratoEnum(str, Enum):
    """Tipos conocidos, incluido ``freelance`` para leer datos heredados."""
    TIEMPO_COMPLETO = "tiempo_completo"
    MEDIO_TIEMPO = "medio_tiempo"
    TEMPORAL = "temporal"
    FREELANCE = "freelance"
    PRACTICAS = "practicas"


TIPOS_CONTRATO_ESCRITURA = frozenset(
    {
        TipoContratoEnum.TIEMPO_COMPLETO,
        TipoContratoEnum.MEDIO_TIEMPO,
        TipoContratoEnum.PRACTICAS,
        TipoContratoEnum.TEMPORAL,
    }
)


def validar_tipo_contrato_escritura(tipo_contrato: TipoContratoEnum) -> None:
    """Impide crear o seleccionar nuevamente categorías descontinuadas."""
    if tipo_contrato not in TIPOS_CONTRATO_ESCRITURA:
        raise ValueError("El tipo de contrato seleccionado no está permitido")


@dataclass
class Requisito:
    """Value Object que representa un requisito para un puesto"""
    tipo: str  # ej: "experiencia", "educación", "habilidad"
    descripcion: str
    es_obligatorio: bool = True


@dataclass
class Puesto:
    """Entity que representa un puesto de trabajo ofertado"""
    puesto_id: UUID = field(default_factory=uuid4)
    empresa_id: UUID = None
    titulo: str = ""
    descripcion: str = ""
    ubicacion: str = ""
    salario_min: Optional[float] = None
    salario_max: Optional[float] = None
    moneda: str = "PEN"
    tipo_contrato: TipoContratoEnum = TipoContratoEnum.TIEMPO_COMPLETO
    fecha_publicacion: datetime = field(default_factory=datetime.now)
    fecha_cierre: Optional[datetime] = None
    estado: EstadoPuestoEnum = EstadoPuestoEnum.ABIERTO
    
    def abrir_puesto(self) -> bool:
        """Abre el puesto para recibir postulaciones"""
        if self.estado == EstadoPuestoEnum.CERRADO:
            self.estado = EstadoPuestoEnum.ABIERTO
            self.fecha_cierre = None
            return True
        return False
    
    def cerrar_puesto(self) -> bool:
        """Cierra el puesto para no recibir más postulaciones"""
        if self.estado == EstadoPuestoEnum.ABIERTO:
            self.estado = EstadoPuestoEnum.CERRADO
            self.fecha_cierre = datetime.now()
            return True
        return False
    
    def actualizar_informacion(self, titulo=None, descripcion=None, 
                              ubicacion=None, salario_min=None, 
                              salario_max=None, moneda=None,
                              tipo_contrato=None,
                              actualizar_salario_min: bool = False,
                              actualizar_salario_max: bool = False) -> None:
        """Actualiza la información básica del puesto"""
        if self.estado == EstadoPuestoEnum.CERRADO:
            raise ValueError("No se puede actualizar una vacante cerrada")

        salario_min_resultante = (
            salario_min if actualizar_salario_min else self.salario_min
        )
        salario_max_resultante = (
            salario_max if actualizar_salario_max else self.salario_max
        )
        if salario_min_resultante is not None and salario_min_resultante < 0:
            raise ValueError("salario_min no puede ser negativo")
        if salario_max_resultante is not None and salario_max_resultante < 0:
            raise ValueError("salario_max no puede ser negativo")
        if (
            salario_min_resultante is not None
            and salario_max_resultante is not None
            and salario_max_resultante < salario_min_resultante
        ):
            raise ValueError("salario_max no puede ser menor que salario_min")
            
        if titulo is not None:
            self.titulo = titulo
        if descripcion is not None:
            self.descripcion = descripcion
        if ubicacion is not None:
            self.ubicacion = ubicacion
        if actualizar_salario_min:
            self.salario_min = salario_min
        if actualizar_salario_max:
            self.salario_max = salario_max
        if moneda is not None:
            self.moneda = moneda
        if tipo_contrato is not None:
            validar_tipo_contrato_escritura(tipo_contrato)
            self.tipo_contrato = tipo_contrato


@dataclass
class PuestoAggregate(AggregateRoot):
    """Aggregate que garantiza la consistencia del puesto y sus requisitos"""
    puesto: Puesto
    requisitos: List[Requisito] = field(default_factory=list)
    
    def agregar_requisito(self, tipo: str, descripcion: str, es_obligatorio: bool = True) -> None:
        """Agrega un nuevo requisito al puesto"""
        if self.puesto.estado == EstadoPuestoEnum.CERRADO:
            raise ValueError("No se pueden agregar requisitos a una vacante cerrada")
            
        requisito = Requisito(tipo=tipo, descripcion=descripcion, es_obligatorio=es_obligatorio)
        self.requisitos.append(requisito)
    
    def actualizar_requisitos(self, nuevos_requisitos: List[Dict[str, Any]]) -> None:
        """Actualiza la lista completa de requisitos"""
        if self.puesto.estado == EstadoPuestoEnum.CERRADO:
            raise ValueError("No se pueden actualizar requisitos de una vacante cerrada")
            
        self.requisitos = [
            Requisito(
                tipo=req.get("tipo", "general"),
                descripcion=req.get("descripcion", ""),
                es_obligatorio=req.get("es_obligatorio", True)
            )
            for req in nuevos_requisitos
        ]
    
    def cambiar_estado(self, nuevo_estado: EstadoPuestoEnum) -> bool:
        """Cambia el estado del puesto (abierto/cerrado)"""
        if nuevo_estado == EstadoPuestoEnum.ABIERTO:
            return self.puesto.abrir_puesto()
        else:
            return self.puesto.cerrar_puesto()


# Eventos de dominio
@dataclass
class PuestoCreado:
    """Evento que se emite cuando se crea un nuevo puesto"""
    puesto_id: UUID
    empresa_id: UUID


@dataclass
class PuestoCerrado:
    """Evento que se emite cuando se cierra un puesto"""
    puesto_id: UUID
    empresa_id: UUID
    fecha_cierre: datetime


@dataclass
class PuestoActualizado:
    """Evento que se emite cuando se actualiza un puesto"""
    puesto_id: UUID
    campos_actualizados: List[str]
