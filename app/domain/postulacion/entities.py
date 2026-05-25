from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
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


@dataclass(frozen=True)
class EstadoPostulacion:
    """Value Object que representa los estados posibles de una postulación"""
    valor: EstadoPostulacionEnum
    
    def es_valido(self, nuevo_estado: str) -> bool:
        """
        Valida si el cambio de estado es permitido según las reglas de negocio
        """
        # Definimos las transiciones de estado permitidas
        transiciones_permitidas = {
            EstadoPostulacionEnum.PENDIENTE: [
                EstadoPostulacionEnum.EN_REVISION, 
                EstadoPostulacionEnum.RECHAZADO,
                EstadoPostulacionEnum.ENTREVISTA,
                EstadoPostulacionEnum.ACEPTADO,
                EstadoPostulacionEnum.OFERTA,
                EstadoPostulacionEnum.RECHAZO
            ],
            EstadoPostulacionEnum.EN_REVISION: [
                EstadoPostulacionEnum.ACEPTADO,
                EstadoPostulacionEnum.RECHAZADO,
                EstadoPostulacionEnum.ENTREVISTA, 
                EstadoPostulacionEnum.OFERTA,
                EstadoPostulacionEnum.RECHAZO
            ],
            EstadoPostulacionEnum.ACEPTADO: [
                EstadoPostulacionEnum.ENTREVISTA,
                EstadoPostulacionEnum.OFERTA,
                EstadoPostulacionEnum.RECHAZADO,
                EstadoPostulacionEnum.RECHAZO
            ],
            EstadoPostulacionEnum.RECHAZADO: [],  # Estado final no permite cambios
            EstadoPostulacionEnum.ENTREVISTA: [
                EstadoPostulacionEnum.OFERTA, 
                EstadoPostulacionEnum.ACEPTADO,
                EstadoPostulacionEnum.RECHAZADO,
                EstadoPostulacionEnum.RECHAZO
            ],
            EstadoPostulacionEnum.OFERTA: [],  # Estado final no permite cambios
            EstadoPostulacionEnum.RECHAZO: [],  # Estado final no permite cambios
        }
        
        try:
            nuevo_estado_enum = EstadoPostulacionEnum(nuevo_estado)
            return nuevo_estado_enum in transiciones_permitidas.get(self.valor, [])
        except ValueError:
            return False


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
        
        self.estado = EstadoPostulacion(nuevo_estado)
        return True
    
    def agregar_documento(self, documento: Dict[str, Any]) -> None:
        """Agrega un documento a la postulación"""
        self.documentos_adjuntos.append(documento)
    
    def registrar_hito(self, descripcion: str, fecha: Optional[datetime] = None) -> None:
        """Registra un nuevo hito en la postulación"""
        # Este método será implementado en el agregado
        pass


class EstadoPublicacionEnum(str, Enum):
    """Valores posibles para el estado de publicación de un puesto"""
    BORRADOR = "borrador"
    PUBLICADO = "publicado"
    CERRADO = "cerrado"


@dataclass
class PuestoPostulacion:
    """Entity que representa un puesto de trabajo creado por una empresa"""
    puesto_id: UUID = field(default_factory=uuid4)
    empresa_id: UUID = None
    titulo: str = ""
    descripcion: str = ""
    requisitos: List[str] = field(default_factory=list)
    fecha_inicio: datetime = field(default_factory=datetime.now)
    fecha_fin: Optional[datetime] = None
    estado_publicacion: EstadoPublicacionEnum = EstadoPublicacionEnum.BORRADOR
    
    def publicar(self) -> bool:
        """Publica el puesto para hacerlo visible a los candidatos"""
        if self.estado_publicacion != EstadoPublicacionEnum.BORRADOR:
            return False
        
        self.estado_publicacion = EstadoPublicacionEnum.PUBLICADO
        return True
    
    def cerrar(self) -> bool:
        """Cierra el puesto para que no reciba más postulaciones"""
        if self.estado_publicacion != EstadoPublicacionEnum.PUBLICADO:
            return False
        
        self.estado_publicacion = EstadoPublicacionEnum.CERRADO
        self.fecha_fin = datetime.now()
        return True
    
    def actualizar_requisitos(self, nuevos_requisitos: List[str]) -> None:
        """Actualiza los requisitos del puesto"""
        if self.estado_publicacion == EstadoPublicacionEnum.BORRADOR:
            self.requisitos = nuevos_requisitos


@dataclass
class PostulacionAggregate(AggregateRoot):
    """Aggregate que garantiza la consistencia entre la postulación, su estado y la línea de tiempo"""
    postulacion: Postulacion
    estado: EstadoPostulacion
    linea_de_tiempo: LineaDeTiempo = field(default_factory=LineaDeTiempo)
    
    def postularse(self) -> None:
        """Registra una nueva postulación"""
        hito = self.linea_de_tiempo.agregar_hito(
            fecha=self.postulacion.fecha_postulacion,
            descripcion=f"Postulación creada en estado {self.estado.valor.value}"
        )
        # Aquí podríamos agregar un evento de dominio
        self.add_event(PostulacionCreada(self.postulacion.postulacion_id))
    
    def cambiar_estado(self, nuevo_estado: str) -> bool:
        estado_anterior = self.estado.valor
        
        try:
            nuevo_estado_enum = EstadoPostulacionEnum(nuevo_estado)
        except ValueError:
            return False
        
        if self.postulacion.actualizar_estado(nuevo_estado_enum):
            self.estado = self.postulacion.estado
            hito = self.linea_de_tiempo.agregar_hito(
                fecha=datetime.now(),
                descripcion=f"Estado actualizado de {estado_anterior.value} a {nuevo_estado_enum.value}"
            )
            # Evento de dominio
            self.add_event(EstadoPostulacionActualizado(
                self.postulacion.postulacion_id,
                estado_anterior.value,
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
