import json
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator, List, Optional
from uuid import UUID
from sqlalchemy import func
from sqlalchemy.orm import Session

from sqlalchemy.exc import IntegrityError

from app.domain.iam.entities import (
    CuentaAggregate, Cuenta, Credencial, Token
)
from app.domain.iam.repositories import CuentaRepository
from app.infrastructure.iam.models import CuentaModel, TokenModel, HistorialAccesoModel
from app.infrastructure.database.connection import SessionLocal


class CuentaRepositoryImpl(CuentaRepository):
    """Implementación del repositorio de cuentas usando SQLAlchemy.

    Cada operación abre y cierra su propia sesión para no retener conexiones
    del pool entre requests. Este repositorio se instancia en cada request
    (incluida la dependencia de autenticación), por lo que mantener una sesión
    viva en el constructor agotaba el QueuePool. Si se inyecta una sesión
    externa (p. ej. en tests), el llamador es responsable de cerrarla.
    """

    def __init__(self, session: Optional[Session] = None):
        self._external_session = session

    @contextmanager
    def _session_scope(self) -> Iterator[Session]:
        if self._external_session is not None:
            yield self._external_session
            return
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def guardar(self, cuenta_aggregate: CuentaAggregate) -> UUID:
        """Guarda o actualiza una cuenta"""
        with self._session_scope() as session:
            try:
                cuenta = cuenta_aggregate.cuenta

                # Buscar si existe
                cuenta_existente = session.query(CuentaModel).filter_by(
                    # ``CuentaModel.id`` usa UUID(as_uuid=True). Convertirlo a
                    # texto rompe el bind en SQLite (y depende del driver en
                    # PostgreSQL), precisamente durante cualquier PATCH de
                    # perfil. El agregado ya conserva un UUID real.
                    id=cuenta.cuenta_id
                ).first()

                if cuenta_existente:
                    # Actualizar
                    cuenta_existente.email = cuenta.credencial.email
                    cuenta_existente.hash_password = cuenta.credencial.hash_password
                    cuenta_existente.nombre_completo = cuenta.nombre_completo
                    cuenta_existente.carrera = cuenta.carrera
                    cuenta_existente.telefono = cuenta.telefono
                    cuenta_existente.ciudad = cuenta.ciudad
                    cuenta_existente.foto_url = cuenta.foto_url
                    cuenta_existente.perfil = (
                        json.dumps(cuenta.perfil) if cuenta.perfil is not None else None
                    )
                    cuenta_existente.rol = cuenta.rol
                    cuenta_existente.estado = cuenta.estado
                    cuenta_existente.fecha_actualizacion = cuenta.fecha_actualizacion
                    cuenta_existente.fecha_primer_acceso = cuenta.fecha_primer_acceso
                    cuenta_existente.intentos_fallidos = cuenta_aggregate.intentos_fallidos
                else:
                    # Crear nueva
                    cuenta_model = CuentaModel(
                        id=cuenta.cuenta_id,
                        nombre_completo=cuenta.nombre_completo,
                        carrera=cuenta.carrera,
                        telefono=cuenta.telefono,
                        ciudad=cuenta.ciudad,
                        foto_url=cuenta.foto_url,
                        perfil=json.dumps(cuenta.perfil) if cuenta.perfil is not None else None,
                        email=cuenta.credencial.email,
                        hash_password=cuenta.credencial.hash_password,
                        rol=cuenta.rol,
                        estado=cuenta.estado,
                        fecha_creacion=cuenta.fecha_creacion,
                        fecha_actualizacion=cuenta.fecha_actualizacion,
                        fecha_primer_acceso=cuenta.fecha_primer_acceso,
                        intentos_fallidos=cuenta_aggregate.intentos_fallidos,
                        activa=True
                    )
                    session.add(cuenta_model)

                # Guardar tokens activos
                for tipo_token, token in cuenta_aggregate.tokens_activos.items():
                    token_existente = session.query(TokenModel).filter_by(
                        id=token.id_token
                    ).first()

                    if not token_existente:
                        token_model = TokenModel(
                            id=token.id_token,
                            cuenta_id=cuenta.cuenta_id,
                            token_value=token.token_value,
                            tipo_token=token.tipo_token,
                            fecha_creacion=token.fecha_creacion,
                            fecha_expiracion=token.fecha_expiracion,
                            activo=token.activo
                        )
                        session.add(token_model)

                # Guardar historial de accesos
                for acceso in cuenta_aggregate.historial_accesos:
                    historial_model = HistorialAccesoModel(
                        cuenta_id=cuenta.cuenta_id,
                        tipo_acceso=acceso['tipo_acceso'],
                        detalles=json.dumps(acceso['detalles']) if acceso.get('detalles') else None,
                        fecha_creacion=acceso['fecha']
                    )
                    session.add(historial_model)

                session.commit()
                return cuenta.cuenta_id

            except IntegrityError as ie:
                session.rollback()
                # Log the actual error to help debugging
                error_detail = str(ie.orig) if ie.orig else str(ie)
                if "email" in error_detail.lower() or "unique" in error_detail.lower():
                    raise ValueError("El email ya está registrado")
                else:
                    raise ValueError(f"Database integrity error: {error_detail}")
            except Exception as e:
                session.rollback()
                raise e

    def obtener_por_id(self, cuenta_id: UUID) -> Optional[CuentaAggregate]:
        """Recupera una cuenta por su ID"""
        with self._session_scope() as session:
            cuenta_model = session.query(CuentaModel).filter_by(
                id=cuenta_id
            ).first()

            if not cuenta_model:
                return None

            return self._mapear_modelo_a_aggregate(session, cuenta_model)

    def obtener_por_email(self, email: str) -> Optional[CuentaAggregate]:
        """Recupera una cuenta por su email"""
        with self._session_scope() as session:
            cuenta_model = session.query(CuentaModel).filter(
                func.lower(CuentaModel.email) == email.strip().lower()
            ).first()

            if not cuenta_model:
                return None

            return self._mapear_modelo_a_aggregate(session, cuenta_model)

    def verificar_email_existe(self, email: str) -> bool:
        """Verifica si un email ya está registrado"""
        with self._session_scope() as session:
            cuenta = session.query(CuentaModel).filter(
                func.lower(CuentaModel.email) == email.strip().lower()
            ).first()
            return cuenta is not None

    def listar_todas(self) -> List[CuentaAggregate]:
        """Lista todas las cuentas"""
        with self._session_scope() as session:
            cuentas_model = session.query(CuentaModel).all()
            return [self._mapear_modelo_a_aggregate(session, m) for m in cuentas_model]

    def revocar_tokens(self, cuenta_id: UUID) -> None:
        """Revoca tokens de acceso/refresco tras un cambio de credenciales."""
        with self._session_scope() as session:
            try:
                session.query(TokenModel).filter(
                    TokenModel.cuenta_id == cuenta_id,
                    TokenModel.tipo_token.in_(("access", "refresh")),
                    TokenModel.activo.is_(True),
                ).update(
                    {TokenModel.activo: False},
                    synchronize_session=False,
                )
                session.commit()
            except Exception:
                session.rollback()
                raise

    def token_esta_activo(
        self,
        token_value: str,
        cuenta_id: UUID,
        tipo_token: str,
    ) -> bool:
        """Comprueba revocacion, pertenencia, tipo y expiracion persistida."""
        with self._session_scope() as session:
            token = session.query(TokenModel).filter(
                TokenModel.token_value == token_value,
                TokenModel.cuenta_id == cuenta_id,
                TokenModel.tipo_token == tipo_token,
                TokenModel.activo.is_(True),
            ).first()
            return bool(
                token
                and (
                    token.fecha_expiracion is None
                    or token.fecha_expiracion >= datetime.now()
                )
            )

    def _mapear_modelo_a_aggregate(self, session: Session, cuenta_model: CuentaModel) -> CuentaAggregate:
        """Mapea un modelo de base de datos a un agregado"""
        # Recuperar tokens asociados
        tokens_model = session.query(TokenModel).filter(
            TokenModel.cuenta_id == cuenta_model.id,
            TokenModel.activo.is_(True),
        ).order_by(TokenModel.fecha_creacion.desc()).all()

        tokens_dict = {}
        for token_model in tokens_model:
            if token_model.tipo_token not in tokens_dict:
                token = Token(
                    id_token=token_model.id,
                    token_value=token_model.token_value,
                    tipo_token=token_model.tipo_token,
                    fecha_creacion=token_model.fecha_creacion,
                    fecha_expiracion=token_model.fecha_expiracion,
                    activo=token_model.activo
                )
                tokens_dict[token_model.tipo_token] = token

        # El historial es append-only. No se hidrata en el agregado porque
        # ``guardar`` persistiria de nuevo cada fila historica en cada login.
        historial = []

        # Crear credencial
        credencial = Credencial(
            id_credencial=cuenta_model.id,
            email=cuenta_model.email,
            hash_password=cuenta_model.hash_password,
            fecha_creacion=cuenta_model.fecha_creacion,
            fecha_ultimo_acceso=cuenta_model.fecha_primer_acceso,
            activa=cuenta_model.activa
        )

        # Crear entidad Cuenta
        perfil_dict = None
        if getattr(cuenta_model, 'perfil', None):
            try:
                perfil_dict = json.loads(cuenta_model.perfil)
            except Exception:
                perfil_dict = None

        cuenta = Cuenta(
            cuenta_id=cuenta_model.id,
            credencial=credencial,
            nombre_completo=cuenta_model.nombre_completo,
            carrera=cuenta_model.carrera,
            telefono=cuenta_model.telefono,
            ciudad=cuenta_model.ciudad,
            foto_url=cuenta_model.foto_url,
            perfil=perfil_dict,
            rol=cuenta_model.rol,
            estado=cuenta_model.estado,
            fecha_creacion=cuenta_model.fecha_creacion,
            fecha_actualizacion=cuenta_model.fecha_actualizacion,
            fecha_primer_acceso=cuenta_model.fecha_primer_acceso
        )

        # Crear agregado
        aggregate = CuentaAggregate(
            cuenta=cuenta,
            tokens_activos=tokens_dict,
            historial_accesos=historial,
            intentos_fallidos=cuenta_model.intentos_fallidos
        )

        return aggregate
