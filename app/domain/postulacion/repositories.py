from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from app.domain.postulacion.entities import PostulacionAggregate


class PostulacionRepository(ABC):
    @abstractmethod
    def guardar(self, postulacion: PostulacionAggregate) -> UUID:
        """Guarda o actualiza una postulacion y devuelve su ID."""
        pass

    @abstractmethod
    def obtener_por_id(
        self, postulacion_id: UUID
    ) -> Optional[PostulacionAggregate]:
        pass

    @abstractmethod
    def obtener_por_candidato(
        self, candidato_id: UUID
    ) -> List[PostulacionAggregate]:
        pass

    @abstractmethod
    def obtener_por_puesto(self, puesto_id: UUID) -> List[PostulacionAggregate]:
        pass
