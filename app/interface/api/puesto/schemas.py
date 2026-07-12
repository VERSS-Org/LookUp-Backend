from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


def _validar_rango_salarial(
    salario_min: Optional[float], salario_max: Optional[float]
) -> None:
    for etiqueta, valor in (("salario_min", salario_min), ("salario_max", salario_max)):
        if valor is not None and valor < 0:
            raise ValueError(f"{etiqueta} no puede ser negativo")
    if salario_min is not None and salario_max is not None and salario_max < salario_min:
        raise ValueError("salario_max no puede ser menor que salario_min")


class EstadoPuestoEnum(str, Enum):
    ABIERTO = "abierto"
    CERRADO = "cerrado"


class TipoContratoEnum(str, Enum):
    TIEMPO_COMPLETO = "tiempo_completo"
    MEDIO_TIEMPO = "medio_tiempo"
    TEMPORAL = "temporal"
    FREELANCE = "freelance"
    PRACTICAS = "practicas"


class RequisitoCreate(BaseModel):
    tipo: str = Field(min_length=1, max_length=100)
    descripcion: str = Field(min_length=1, max_length=1000)
    es_obligatorio: bool = True

    @field_validator("tipo", "descripcion")
    @classmethod
    def validar_texto(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("El requisito no puede estar vacío")
        return value


class RequisitoResponse(BaseModel):
    tipo: str
    descripcion: str
    es_obligatorio: bool


class PuestoCreate(BaseModel):
    empresa_id: str
    titulo: str = Field(min_length=1, max_length=300)
    descripcion: str = Field(min_length=1, max_length=5000)
    ubicacion: str = Field(min_length=1, max_length=300)
    salario_min: Optional[float] = None
    salario_max: Optional[float] = None
    moneda: str = Field("PEN", min_length=3, max_length=10)
    tipo_contrato: TipoContratoEnum = TipoContratoEnum.TIEMPO_COMPLETO
    requisitos: List[RequisitoCreate] = Field(default_factory=list)

    @field_validator("titulo", "descripcion", "ubicacion")
    @classmethod
    def validar_texto_no_vacio(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("El campo no puede estar vacío")
        return value

    @field_validator("moneda")
    @classmethod
    def normalizar_moneda(cls, value: str) -> str:
        return value.strip().upper()

    @model_validator(mode="after")
    def validar_salarios(self):
        _validar_rango_salarial(self.salario_min, self.salario_max)
        return self


class PuestoUpdate(BaseModel):
    titulo: Optional[str] = Field(None, min_length=1, max_length=300)
    descripcion: Optional[str] = Field(None, min_length=1, max_length=5000)
    ubicacion: Optional[str] = Field(None, min_length=1, max_length=300)
    salario_min: Optional[float] = None
    salario_max: Optional[float] = None
    moneda: Optional[str] = Field(None, min_length=3, max_length=10)
    tipo_contrato: Optional[TipoContratoEnum] = None
    requisitos: Optional[List[RequisitoCreate]] = None

    @field_validator("titulo", "descripcion", "ubicacion")
    @classmethod
    def validar_texto_no_vacio(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("El campo no puede estar vacío")
        return value

    @field_validator("moneda")
    @classmethod
    def normalizar_moneda(cls, value: Optional[str]) -> Optional[str]:
        return value.strip().upper() if value is not None else None

    @model_validator(mode="after")
    def validar_salarios(self):
        _validar_rango_salarial(self.salario_min, self.salario_max)
        return self


class PuestoResponse(BaseModel):
    puesto_id: str
    empresa_id: str
    empresa_nombre: Optional[str] = None
    empresa_foto: Optional[str] = None
    titulo: str
    descripcion: str
    ubicacion: str
    salario_min: Optional[float]
    salario_max: Optional[float]
    moneda: str
    tipo_contrato: str
    fecha_publicacion: datetime
    fecha_cierre: Optional[datetime]
    estado: str
    requisitos: List[RequisitoResponse]


class EstadoPuestoUpdate(BaseModel):
    nuevo_estado: EstadoPuestoEnum
