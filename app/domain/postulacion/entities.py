from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any
from uuid import UUID, uuid4

from app.domain.common import AggregateRoot


class EstadoPostulacionEnum(str, Enum):
    """Valores posibles para el estado de una postulación"""
    PENDIENTE = "pendiente"
    EN_REVISION = "en_revision"
    RECHAZADO = "rechazado"
    ACEPTADO = "aceptado"
    ENTREVISTA = "entrevista"
    OFERTA = "oferta"
    RECHAZO = "rechazo"


ESTADOS_POSTULACION_CANONICOS = {
    "pendiente",
    "en_revision",
    "entrevista",
    "aceptado",
    "rechazado",
}

ALIASES_ESTADO_POSTULACION = {
    "oferta": "aceptado",
    "rechazo": "rechazado",
}


def normalizar_estado_postulacion(estado: object) -> str:
    """Devuelve la terminologia publica canonica de un estado.

    ``oferta`` y ``rechazo`` se conservan para leer datos y clientes antiguos,
    pero no deben propagarse como estados nuevos en la API.
    """
    valor = estado.value if isinstance(estado, EstadoPostulacionEnum) else str(estado)
    valor = valor.strip().lower()
    return ALIASES_ESTADO_POSTULACION.get(valor, valor)


@dataclass(frozen=True)
class EstadoPostulacion:
    """Value Object que representa los estados posibles de una postulación"""
    valor: EstadoPostulacionEnum
    
    def es_valido(self, nuevo_estado: str) -> bool:
        """
        Valida si el cambio de estado es permitido según las reglas de negocio
        """
        estado_actual = normalizar_estado_postulacion(self.valor)
        estado_nuevo = normalizar_estado_postulacion(nuevo_estado)
        if estado_nuevo not in ESTADOS_POSTULACION_CANONICOS:
            return False

        transiciones_permitidas = {
            "pendiente": {"en_revision", "entrevista", "aceptado", "rechazado"},
            "en_revision": {"entrevista", "aceptado", "rechazado"},
            "entrevista": {"aceptado", "rechazado"},
            "aceptado": set(),
            "rechazado": set(),
        }
        return estado_nuevo in transiciones_permitidas.get(estado_actual, set())


@dataclass
class Hito:
    """Entity que representa un evento relevante dentro de la postulación"""
    hito_id: UUID = field(default_factory=uuid4)
    fecha: datetime = field(default_factory=datetime.now)
    descripcion: str = ""
    
    def actualizar_descripcion(self, nueva_descripcion: str) -> None:
        """Actualiza la descripción del hito"""
        self.descripcion = nueva_descripcion
        
    def cambiar_fecha(self, nueva_fecha: datetime) -> None:
        """Cambia la fecha del hito"""
        self.fecha = nueva_fecha


@dataclass
class LineaDeTiempo:
    """Value Object que registra los hitos relevantes de una postulación"""
    lista_hitos: List[Hito] = field(default_factory=list)
    
    def agregar_hito(self, fecha: datetime, descripcion: str) -> Hito:
        """Agrega un nuevo hito a la línea de tiempo"""
        hito = Hito(fecha=fecha, descripcion=descripcion)
        self.lista_hitos.append(hito)
        return hito


@dataclass
class Postulacion:
    """Entity que representa la solicitud de un candidato a un puesto"""
    postulacion_id: UUID = field(default_factory=uuid4)
    candidato_id: UUID = None
    puesto_id: UUID = None
    fecha_postulacion: datetime = field(default_factory=datetime.now)
    estado: EstadoPostulacion = field(default_factory=lambda: EstadoPostulacion(EstadoPostulacionEnum.PENDIENTE))
    documentos_adjuntos: List[Dict[str, Any]] = field(default_factory=list)
    
    def actualizar_estado(self, nuevo_estado: EstadoPostulacionEnum) -> bool:
        """Actualiza el estado de la postulación"""
        if not self.estado.es_valido(nuevo_estado):
            return False
        
        self.estado = EstadoPostulacion(
            EstadoPostulacionEnum(normalizar_estado_postulacion(nuevo_estado))
        )
        return True
    
    def agregar_documento(self, documento: Dict[str, Any]) -> None:
        """Agrega un documento a la postulación"""
        self.documentos_adjuntos.append(documento)
    
@dataclass
class PostulacionAggregate(AggregateRoot):
    """Aggregate que garantiza la consistencia entre la postulación, su estado y la línea de tiempo"""
    postulacion: Postulacion
    estado: EstadoPostulacion
    linea_de_tiempo: LineaDeTiempo = field(default_factory=LineaDeTiempo)
    
    def postularse(self) -> None:
        """Registra una nueva postulación"""
        self.linea_de_tiempo.agregar_hito(
            fecha=self.postulacion.fecha_postulacion,
            descripcion=f"Postulación creada en estado {self.estado.valor.value}"
        )
        # Aquí podríamos agregar un evento de dominio
        self.add_event(PostulacionCreada(self.postulacion.postulacion_id))
    
    def cambiar_estado(self, nuevo_estado: str) -> bool:
        estado_anterior = self.estado.valor
        
        try:
            nuevo_estado_enum = EstadoPostulacionEnum(
                normalizar_estado_postulacion(nuevo_estado)
            )
        except ValueError:
            return False
        
        if self.postulacion.actualizar_estado(nuevo_estado_enum):
            self.estado = self.postulacion.estado
            self.linea_de_tiempo.agregar_hito(
                fecha=datetime.now(),
                descripcion=(
                    "Estado actualizado de "
                    f"{normalizar_estado_postulacion(estado_anterior)} "
                    f"a {nuevo_estado_enum.value}"
                )
            )
            # Evento de dominio
            self.add_event(EstadoPostulacionActualizado(
                self.postulacion.postulacion_id,
                normalizar_estado_postulacion(estado_anterior),
                nuevo_estado_enum.value
            ))
            return True
        return False
    
    def registrar_evento(self, descripcion: str) -> None:
        """Registra un evento genérico en la línea de tiempo de la postulación"""
        self.linea_de_tiempo.agregar_hito(
            fecha=datetime.now(),
            descripcion=descripcion
        )


# Eventos de dominio
@dataclass
class PostulacionCreada:
    """Evento que se emite cuando se crea una nueva postulación"""
    postulacion_id: UUID


@dataclass
class EstadoPostulacionActualizado:
    """Evento que se emite cuando el estado de la postulación cambia"""
    postulacion_id: UUID
    estado_anterior: str
    estado_nuevo: str
