from typing import List, Optional
from uuid import UUID

from app.domain.puesto.entities import PuestoAggregate
from app.domain.puesto.repositories import PuestoRepository
from app.infrastructure.database.connection import SessionLocal
from app.infrastructure.puesto.models import (
    PuestoMapeo,
    PuestoModel,
    RequisitoPuestoModel,
)


class PuestoRepositoryImpl(PuestoRepository):
    """
    Implementación del repositorio de puestos con SQLAlchemy
    La BD actual solo tiene columnas: id (INTEGER), titulo, empresa, descripcion, estado
    Usamos una tabla de mapeo para enlazar UUIDs del dominio a IDs de BD
    """
    
    @staticmethod
    def _reemplazar_requisitos(
        puesto_db: PuestoModel, puesto_aggregate: PuestoAggregate
    ) -> None:
        puesto_db.requisitos = [
            RequisitoPuestoModel(
                tipo=requisito.tipo,
                descripcion=requisito.descripcion,
                es_obligatorio=requisito.es_obligatorio,
            )
            for requisito in puesto_aggregate.requisitos
        ]
    
    def guardar(self, puesto_aggregate: PuestoAggregate) -> UUID:
        """Guarda o actualiza un puesto y devuelve su ID"""
        db = SessionLocal()
        try:
            puesto = puesto_aggregate.puesto
            puesto_id = puesto.puesto_id
            empresa_id_str = str(puesto.empresa_id)
            puesto_id_str = str(puesto_id)
            
            # Buscar el mapeo existente
            mapeo_existente = db.query(PuestoMapeo).filter(
                PuestoMapeo.uuid_id == puesto_id_str
            ).first()
            
            if mapeo_existente:
                # UPDATE: El puesto ya existe, solo actualizar sus datos
                puesto_db = db.query(PuestoModel).filter(
                    PuestoModel.id == mapeo_existente.bd_id
                ).first()
                if not puesto_db:
                    raise ValueError("El mapeo de la vacante apunta a un registro inexistente")
                puesto_db.titulo = puesto.titulo
                puesto_db.empresa = empresa_id_str
                puesto_db.descripcion = puesto.descripcion
                puesto_db.ubicacion = puesto.ubicacion
                puesto_db.salario_min = puesto.salario_min
                puesto_db.salario_max = puesto.salario_max
                puesto_db.moneda = puesto.moneda
                puesto_db.tipo_contrato = puesto.tipo_contrato.value if hasattr(puesto.tipo_contrato, 'value') else str(puesto.tipo_contrato)
                puesto_db.fecha_publicacion = puesto.fecha_publicacion
                puesto_db.fecha_cierre = puesto.fecha_cierre
                puesto_db.estado = puesto.estado.value if hasattr(puesto.estado, 'value') else str(puesto.estado)
                self._reemplazar_requisitos(puesto_db, puesto_aggregate)
                db.commit()
            else:
                # INSERT: Nuevo puesto
                puesto_db = PuestoModel(
                    titulo=puesto.titulo,
                    empresa=empresa_id_str,
                    descripcion=puesto.descripcion,
                    ubicacion=puesto.ubicacion,
                    salario_min=puesto.salario_min,
                    salario_max=puesto.salario_max,
                    moneda=puesto.moneda,
                    tipo_contrato=puesto.tipo_contrato.value if hasattr(puesto.tipo_contrato, 'value') else str(puesto.tipo_contrato),
                    fecha_publicacion=puesto.fecha_publicacion,
                    fecha_cierre=puesto.fecha_cierre,
                    estado=puesto.estado.value if hasattr(puesto.estado, 'value') else (puesto.estado or "abierto")
                )
                self._reemplazar_requisitos(puesto_db, puesto_aggregate)
                db.add(puesto_db)
                db.flush()  # Obtener el ID autogenerado
                
                # Guardar mapeo
                mapeo = PuestoMapeo(
                    uuid_id=puesto_id_str,
                    bd_id=puesto_db.id
                )
                db.add(mapeo)
                db.commit()
            
            return puesto_id
            
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    def obtener_por_id(self, puesto_id: UUID) -> Optional[PuestoAggregate]:
        """Recupera un puesto por su ID"""
        db = SessionLocal()
        try:
            puesto_id_str = str(puesto_id)
            
            # Buscar el mapeo
            mapeo = db.query(PuestoMapeo).filter(
                PuestoMapeo.uuid_id == puesto_id_str
            ).first()
            
            if not mapeo:
                return None
            
            # Buscar el puesto por bd_id
            puesto_db = db.query(PuestoModel).filter(
                PuestoModel.id == mapeo.bd_id
            ).first()
            
            if not puesto_db:
                return None
            
            from app.domain.puesto.entities import (
                EstadoPuestoEnum,
                Puesto,
                Requisito,
                TipoContratoEnum,
            )
            
            try:
                empresa_id = UUID(puesto_db.empresa)
            except (TypeError, ValueError):
                empresa_id = UUID('00000000-0000-0000-0000-000000000000')
            
            # Convertir tipo_contrato y estado a enums
            try:
                tipo_contrato = TipoContratoEnum(puesto_db.tipo_contrato) if puesto_db.tipo_contrato else TipoContratoEnum.TIEMPO_COMPLETO
            except (TypeError, ValueError):
                tipo_contrato = TipoContratoEnum.TIEMPO_COMPLETO
            
            try:
                estado = EstadoPuestoEnum(puesto_db.estado) if puesto_db.estado else EstadoPuestoEnum.ABIERTO
            except (TypeError, ValueError):
                estado = EstadoPuestoEnum.ABIERTO
            
            puesto = Puesto(
                puesto_id=puesto_id,
                empresa_id=empresa_id,
                titulo=puesto_db.titulo,
                descripcion=puesto_db.descripcion,
                ubicacion=puesto_db.ubicacion or "",
                salario_min=puesto_db.salario_min,
                salario_max=puesto_db.salario_max,
                moneda=puesto_db.moneda or "PEN",
                tipo_contrato=tipo_contrato,
                fecha_publicacion=puesto_db.fecha_publicacion,
                fecha_cierre=puesto_db.fecha_cierre,
                estado=estado
            )
            
            requisitos = [
                Requisito(
                    tipo=requisito.tipo,
                    descripcion=requisito.descripcion,
                    es_obligatorio=requisito.es_obligatorio,
                )
                for requisito in puesto_db.requisitos
            ]
            puesto_aggregate = PuestoAggregate(
                puesto=puesto,
                requisitos=requisitos,
            )
            return puesto_aggregate
            
        finally:
            db.close()
    
    def listar_por_empresa(self, empresa_id: UUID) -> List[PuestoAggregate]:
        """Lista los puestos de una empresa específica"""
        db = SessionLocal()
        try:
            empresa_id_str = str(empresa_id)
            puestos_db = db.query(PuestoModel).filter(
                PuestoModel.empresa == empresa_id_str
            ).all()
            
            resultado = []
            for puesto_db in puestos_db:
                try:
                    # Obtener el UUID del mapeo
                    mapeo = db.query(PuestoMapeo).filter(
                        PuestoMapeo.bd_id == puesto_db.id
                    ).first()
                    if mapeo:
                        puesto_agg = self.obtener_por_id(UUID(mapeo.uuid_id))
                        if puesto_agg:
                            resultado.append(puesto_agg)
                except (TypeError, ValueError):
                    pass
            
            return resultado
            
        finally:
            db.close()
    
    def listar_por_estado(self, estado: str) -> List[PuestoAggregate]:
        """Lista los puestos según su estado"""
        db = SessionLocal()
        try:
            puestos_db = db.query(PuestoModel).filter(
                PuestoModel.estado == estado
            ).all()
            
            resultado = []
            for puesto_db in puestos_db:
                try:
                    mapeo = db.query(PuestoMapeo).filter(
                        PuestoMapeo.bd_id == puesto_db.id
                    ).first()
                    if mapeo:
                        puesto_agg = self.obtener_por_id(UUID(mapeo.uuid_id))
                        if puesto_agg:
                            resultado.append(puesto_agg)
                except (TypeError, ValueError):
                    pass
            
            return resultado
            
        finally:
            db.close()
    
    def listar_todos(self) -> List[PuestoAggregate]:
        """Lista todos los puestos"""
        db = SessionLocal()
        try:
            puestos_db = db.query(PuestoModel).all()
            
            resultado = []
            for puesto_db in puestos_db:
                try:
                    mapeo = db.query(PuestoMapeo).filter(
                        PuestoMapeo.bd_id == puesto_db.id
                    ).first()
                    if mapeo:
                        puesto_agg = self.obtener_por_id(UUID(mapeo.uuid_id))
                        if puesto_agg:
                            resultado.append(puesto_agg)
                except (TypeError, ValueError):
                    pass
            
            return resultado
            
        finally:
            db.close()
    
    def eliminar(self, puesto_id: UUID) -> bool:
        """Elimina un puesto por su ID"""
        db = SessionLocal()
        try:
            puesto_id_str = str(puesto_id)
            
            # Buscar el mapeo
            mapeo = db.query(PuestoMapeo).filter(
                PuestoMapeo.uuid_id == puesto_id_str
            ).first()
            
            if not mapeo:
                return False
            
            # Eliminar de BD
            puesto_db = db.query(PuestoModel).filter(
                PuestoModel.id == mapeo.bd_id
            ).first()
            
            if puesto_db:
                db.delete(puesto_db)
            
            # Eliminar mapeo
            db.delete(mapeo)
            db.commit()
            
            return True
            
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
