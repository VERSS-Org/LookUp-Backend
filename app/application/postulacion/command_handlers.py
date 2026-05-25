from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from uuid import UUID

from app.domain.common import Command, CommandHandler
from app.domain.postulacion.entities import (
    Postulacion, PuestoPostulacion, PostulacionAggregate, 
    EstadoPostulacion, EstadoPostulacionEnum, LineaDeTiempo,
    EstadoPublicacionEnum
)
from app.domain.postulacion.repositories import PostulacionRepository, PuestoPostulacionRepository
from app.domain.puesto.entities import EstadoPuestoEnum
from app.domain.puesto.repositories import PuestoRepository


@dataclass
class PostularCommand(Command):
    """Comando para postular a un puesto"""
    candidato_id: UUID
    puesto_id: UUID
    documentos_adjuntos: List[Dict[str, Any]] = None


class PostularHandler(CommandHandler):
    """
    Manejador del comando para que un candidato postule a un puesto
    """
    
    def __init__(self, 
                 postulacion_repository: PostulacionRepository,
                 puesto_repository: PuestoRepository = None):
        self.postulacion_repository = postulacion_repository
        # Usar PuestoRepository si se proporciona, si no usar el anterior
        self.puesto_repository = puesto_repository
    
    def handle(self, command: PostularCommand) -> UUID:
        """
        Maneja el comando de postulación
        """
        # Validar que el puesto existe y está publicado
        puesto = self.puesto_repository.obtener_por_id(command.puesto_id)
        estado_puesto = (
            puesto.puesto.estado.value
            if puesto and hasattr(puesto.puesto.estado, "value")
            else puesto.puesto.estado if puesto else None
        )
        if not puesto or estado_puesto != EstadoPuestoEnum.ABIERTO.value:
            raise ValueError("El puesto no existe o no esta disponible para postulacion")
        
        # Crear nueva postulación
        postulaciones_existentes = self.postulacion_repository.obtener_por_candidato(
            command.candidato_id
        )
        if any(
            postulacion.postulacion.puesto_id == command.puesto_id
            for postulacion in postulaciones_existentes
        ):
            raise ValueError("Ya existe una postulacion para este puesto")

        postulacion = Postulacion(
            candidato_id=command.candidato_id,
            puesto_id=command.puesto_id,
            documentos_adjuntos=command.documentos_adjuntos or []
        )
        
        estado = EstadoPostulacion(EstadoPostulacionEnum.PENDIENTE)
        linea_tiempo = LineaDeTiempo()
        
        # Crear agregado
        postulacion_aggregate = PostulacionAggregate(
            postulacion=postulacion,
            estado=estado,
            linea_de_tiempo=linea_tiempo
        )
        
        # Registrar la postulación inicial
        postulacion_aggregate.postularse()
        
        # Guardar en repositorio
        postulacion_id = self.postulacion_repository.guardar(postulacion_aggregate)
        
        return postulacion_id


@dataclass
class ActualizarEstadoCommand(Command):
    """Comando para actualizar el estado de una postulación"""
    postulacion_id: UUID
    nuevo_estado: str


class ActualizarEstadoPostulacionHandler(CommandHandler):
    """
    Manejador del comando para actualizar el estado de una postulación
    """
    
    def __init__(self, postulacion_repository: PostulacionRepository):
        self.postulacion_repository = postulacion_repository
    
    def handle(self, command: ActualizarEstadoCommand) -> bool:
        """
        Maneja el comando de actualización de estado
        """
        # Recuperar la postulación
        postulacion_aggregate = self.postulacion_repository.obtener_por_id(command.postulacion_id)
        if not postulacion_aggregate:
            raise ValueError(f"No existe una postulación con ID {command.postulacion_id}")
        
        # Intentar cambiar el estado
        resultado = postulacion_aggregate.cambiar_estado(command.nuevo_estado)
        if not resultado:
            return False
        
        # Guardar los cambios
        self.postulacion_repository.guardar(postulacion_aggregate)
        
        return True


@dataclass
class RegistrarPuestoCommand(Command):
    """Comando para registrar un nuevo puesto de postulación"""
    empresa_id: UUID
    titulo: str
    descripcion: str
    requisitos: List[str]
    fecha_inicio: Optional[str] = None
    fecha_fin: Optional[str] = None


class RegistrarPuestoHandler(CommandHandler):
    """
    Manejador del comando para registrar un nuevo puesto
    """
    
    def __init__(self, puesto_repository: PuestoPostulacionRepository):
        self.puesto_repository = puesto_repository
    
    def handle(self, command: RegistrarPuestoCommand) -> UUID:
        """
        Maneja el comando de registro de puesto
        """
        # Crear nuevo puesto
        puesto = PuestoPostulacion(
            empresa_id=command.empresa_id,
            titulo=command.titulo,
            descripcion=command.descripcion,
            requisitos=command.requisitos
        )
        
        # Guardar en repositorio
        puesto_id = self.puesto_repository.guardar(puesto)
        
        return puesto_id


@dataclass
class PublicarPuestoCommand(Command):
    """Comando para publicar un puesto"""
    puesto_id: UUID


class PublicarPuestoHandler(CommandHandler):
    """
    Manejador del comando para publicar un puesto
    """
    
    def __init__(self, puesto_repository: PuestoPostulacionRepository):
        self.puesto_repository = puesto_repository
    
    def handle(self, command: PublicarPuestoCommand) -> bool:
        """
        Maneja el comando de publicación de puesto
        """
        # Recuperar el puesto
        puesto = self.puesto_repository.obtener_por_id(command.puesto_id)
        if not puesto:
            raise ValueError(f"No existe un puesto con ID {command.puesto_id}")
        
        # Publicar el puesto
        resultado = puesto.publicar()
        if not resultado:
            return False
        
        # Guardar los cambios
        self.puesto_repository.guardar(puesto)
        
        return True


@dataclass
class ActualizarEstadoReclutadorCommand(Command):
    """
    Comando para actualizar el estado de postulación según revisión del reclutador
    US21: Actualizar estado de postulación según revisión del reclutador
    """
    postulacion_id: UUID
    nuevo_estado: str
    comentario_reclutador: str


class ActualizarEstadoReclutadorHandler(CommandHandler):
    """
    Manejador del comando para actualizar el estado de una postulación por un reclutador
    """
    
    def __init__(self, postulacion_repository: PostulacionRepository):
        self.postulacion_repository = postulacion_repository
    
    def handle(self, command: ActualizarEstadoReclutadorCommand) -> bool:
        """
        Maneja el comando de actualización de estado por reclutador
        """
        return self.postulacion_repository.actualizar_estado_postulacion(
            command.postulacion_id,
            command.nuevo_estado,
            f"Actualización por reclutador: {command.comentario_reclutador}"
        )


@dataclass
class SubirDocumentoPerfilCommand(Command):
    """
    Comando para subir un documento al perfil
    US18: Subir documentos al perfil
    """
    cuenta_id: UUID
    documento: dict  # Contiene nombre, tipo, url, etc.


@dataclass
class EliminarDocumentoPerfilCommand(Command):
    """
    Comando para eliminar un documento del perfil
    US19: Eliminar documento del perfil
    """
    cuenta_id: UUID
    documento_id: str


@dataclass
class CompletarPerfilBasicoCommand(Command):
    """
    Comando para completar perfil básico del postulante
    US12: Completar perfil básico del postulante
    """
    cuenta_id: UUID
    datos_basicos: dict  # Contiene nombre, apellido, descripción, etc.
