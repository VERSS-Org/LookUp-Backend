from abc import ABC, abstractmethod
from typing import List

class Command:
    pass

class Query:
    pass

class Event:
    pass

class CommandHandler(ABC):
    @abstractmethod
    def handle(self, command: Command):
        pass

class QueryHandler(ABC):
    @abstractmethod
    def handle(self, query: Query):
        pass

class EventHandler(ABC):
    @abstractmethod
    def handle(self, event: Event):
        pass

class Repository(ABC):
    pass

class AggregateRoot:
    """Base de agregado con eventos aislados por instancia.

    La lista anterior era un atributo de clase, por lo que un evento agregado
    a una cuenta tambien aparecia en puestos y postulaciones creados despues.
    Las subclases son ``dataclass`` y no invocan un ``__init__`` de esta base;
    por eso el almacenamiento se inicializa de forma perezosa.
    """

    def _eventos(self) -> List[Event]:
        if "_events" not in self.__dict__:
            self.__dict__["_events"] = []
        return self.__dict__["_events"]

    def add_event(self, event: Event):
        self._eventos().append(event)
    
    def clear_events(self):
        self._eventos().clear()
    
    def get_events(self) -> List[Event]:
        return self._eventos().copy()
