import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.domain.common import AggregateRoot, Event
from app.domain.iam.entities import EstadoCuentaEnum, RolEnum
from app.application.iam.query_handlers import (
    VerificarTokenQuery,
    VerificarTokenQueryHandler,
)
from app.application.iam.command_handlers import CrearCuentaCommand, CrearCuentaHandler
from app.domain.iam.entities import Cuenta, CuentaAggregate
from app.infrastructure.metrica.repositories import MetricaRepositoryImpl
from app.domain.postulacion.entities import (
    EstadoPostulacion,
    EstadoPostulacionEnum,
    LineaDeTiempo,
    Postulacion,
    PostulacionAggregate,
)
from app.domain.puesto.entities import Puesto, PuestoAggregate, Requisito
from app.infrastructure.database.connection import Base
from app.infrastructure.iam.models import (
    CuentaModel,
    HistorialAccesoModel,
    TokenModel,
)
from app.infrastructure.iam.repositories import CuentaRepositoryImpl
from app.infrastructure.iam.security import TokenManager
from app.infrastructure.postulacion.models import HitoModel, PostulacionModel
from app.infrastructure.postulacion.repositories import PostulacionRepositoryImpl
from app.infrastructure.puesto.models import (
    PuestoMapeo,
    PuestoModel,
    RequisitoPuestoModel,
)
from app.infrastructure.puesto.repositories import PuestoRepositoryImpl
from app.interface.api import dependencies
from app.interface.api.iam import router as iam_router


def _sqlite_session(tables):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=tables)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def test_estados_legacy_se_normalizan_y_los_finales_son_terminales():
    pendiente = EstadoPostulacion(EstadoPostulacionEnum.PENDIENTE)
    assert pendiente.es_valido("oferta")
    assert pendiente.es_valido("rechazo")

    aggregate = PostulacionAggregate(
        postulacion=Postulacion(estado=pendiente),
        estado=pendiente,
        linea_de_tiempo=LineaDeTiempo(),
    )
    assert aggregate.cambiar_estado("oferta")
    assert aggregate.estado.valor == EstadoPostulacionEnum.ACEPTADO
    assert not aggregate.cambiar_estado("entrevista")
    assert not aggregate.cambiar_estado("rechazado")

    rechazado_legado = EstadoPostulacion(EstadoPostulacionEnum.RECHAZO)
    assert not rechazado_legado.es_valido("aceptado")


def test_tokens_generados_son_unicos_y_el_historial_usa_datetime():
    datos = {"sub": str(uuid4()), "tipo": "access"}
    assert TokenManager.crear_access_token(datos) != TokenManager.crear_access_token(
        datos
    )

    aggregate = CuentaAggregate(cuenta=Cuenta())
    aggregate.aplicar_login_exitoso()
    assert isinstance(aggregate.historial_accesos[0]["fecha"], datetime)


def test_registro_crea_cuenta_activa_sin_verificacion_ficticia():
    class Repositorio:
        aggregate = None

        @staticmethod
        def verificar_email_existe(_email):
            return False

        def guardar(self, aggregate):
            self.aggregate = aggregate
            return aggregate.cuenta.cuenta_id

    repository = Repositorio()
    CrearCuentaHandler(repository).handle(
        CrearCuentaCommand(
            nombre_completo="Ana Torres",
            email="ana@example.com",
            password="Demo123!",
        )
    )

    assert repository.aggregate.cuenta.estado == EstadoCuentaEnum.ACTIVA


def test_eventos_de_agregados_no_se_comparten():
    primero = AggregateRoot()
    segundo = AggregateRoot()
    evento = Event()

    primero.add_event(evento)

    assert primero.get_events() == [evento]
    assert segundo.get_events() == []


def test_requisitos_de_vacante_se_persisten_y_actualizan(monkeypatch):
    Session = _sqlite_session(
        [
            PuestoModel.__table__,
            RequisitoPuestoModel.__table__,
            PuestoMapeo.__table__,
        ]
    )
    import app.infrastructure.puesto.repositories as repository_module

    monkeypatch.setattr(repository_module, "SessionLocal", Session)
    repository = PuestoRepositoryImpl()
    puesto = Puesto(empresa_id=uuid4(), titulo="Backend", descripcion="API")
    aggregate = PuestoAggregate(
        puesto=puesto,
        requisitos=[
            Requisito(
                tipo="experiencia",
                descripcion="Dos anos con Python",
                es_obligatorio=True,
            )
        ],
    )

    repository.guardar(aggregate)
    recuperado = repository.obtener_por_id(puesto.puesto_id)
    assert [r.descripcion for r in recuperado.requisitos] == ["Dos anos con Python"]

    recuperado.actualizar_requisitos(
        [
            {
                "tipo": "habilidad",
                "descripcion": "FastAPI",
                "es_obligatorio": False,
            }
        ]
    )
    repository.guardar(recuperado)
    actualizado = repository.obtener_por_id(puesto.puesto_id)
    assert [(r.descripcion, r.es_obligatorio) for r in actualizado.requisitos] == [
        ("FastAPI", False)
    ]


def test_salarios_explicitos_null_se_limpian_y_el_rango_final_se_valida():
    puesto = Puesto(
        empresa_id=uuid4(),
        titulo="Backend",
        descripcion="API",
        salario_min=2000,
        salario_max=4000,
    )

    puesto.actualizar_informacion(
        salario_min=None,
        actualizar_salario_min=True,
    )
    assert puesto.salario_min is None
    assert puesto.salario_max == 4000

    puesto.salario_min = 2000
    with pytest.raises(ValueError):
        puesto.actualizar_informacion(
            salario_max=1000,
            actualizar_salario_max=True,
        )


def test_documentos_de_postulacion_se_persisten(monkeypatch):
    Session = _sqlite_session(
        [PostulacionModel.__table__, HitoModel.__table__]
    )
    import app.infrastructure.postulacion.repositories as repository_module

    monkeypatch.setattr(repository_module, "SessionLocal", Session)
    repository = PostulacionRepositoryImpl()
    estado = EstadoPostulacion(EstadoPostulacionEnum.PENDIENTE)
    aggregate = PostulacionAggregate(
        postulacion=Postulacion(
            candidato_id=uuid4(),
            puesto_id=uuid4(),
            estado=estado,
            documentos_adjuntos=[{"nombre": "cv.pdf", "url": "/cv.pdf"}],
        ),
        estado=estado,
        linea_de_tiempo=LineaDeTiempo(),
    )

    repository.guardar(aggregate)
    recuperado = repository.obtener_por_id(aggregate.postulacion.postulacion_id)

    assert recuperado.postulacion.documentos_adjuntos == [
        {"nombre": "cv.pdf", "url": "/cv.pdf"}
    ]


def test_solo_access_token_activo_autentica_y_revocacion_es_efectiva(monkeypatch):
    Session = _sqlite_session(
        [
            CuentaModel.__table__,
            TokenModel.__table__,
            HistorialAccesoModel.__table__,
        ]
    )
    import app.infrastructure.iam.repositories as repository_module

    monkeypatch.setattr(dependencies, "SessionLocal", Session)
    monkeypatch.setattr(repository_module, "SessionLocal", Session)

    cuenta_id = uuid4()
    access_token = TokenManager.crear_access_token(
        {"sub": str(cuenta_id), "email": "user@example.com", "tipo": "access"}
    )
    refresh_token = TokenManager.crear_refresh_token(
        {"sub": str(cuenta_id), "email": "user@example.com", "tipo": "refresh"}
    )
    with Session() as db:
        db.add(
            CuentaModel(
                id=cuenta_id,
                email="user@example.com",
                hash_password="hash",
                nombre_completo="Usuario",
                rol=RolEnum.POSTULANTE,
                estado=EstadoCuentaEnum.ACTIVA,
                fecha_creacion=datetime.now(),
            )
        )
        db.add(
            TokenModel(
                cuenta_id=cuenta_id,
                token_value=access_token,
                tipo_token="access",
                fecha_creacion=datetime.now(),
                fecha_expiracion=datetime.now() + timedelta(minutes=30),
                activo=True,
            )
        )
        db.add(
            TokenModel(
                cuenta_id=cuenta_id,
                token_value=refresh_token,
                tipo_token="refresh",
                fecha_creacion=datetime.now(),
                fecha_expiracion=datetime.now() + timedelta(days=7),
                activo=True,
            )
        )
        db.commit()

    usuario = asyncio.run(
        dependencies.obtener_usuario_actual(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials=access_token)
        )
    )
    assert usuario["cuenta_id"] == str(cuenta_id)

    repository = CuentaRepositoryImpl()
    verificador = VerificarTokenQueryHandler(repository)
    assert verificador.handle(VerificarTokenQuery(token=access_token))["valido"]

    with pytest.raises(HTTPException) as refresh_error:
        asyncio.run(
            dependencies.obtener_usuario_actual(
                HTTPAuthorizationCredentials(
                    scheme="Bearer", credentials=refresh_token
                )
            )
        )
    assert refresh_error.value.status_code == 401

    repository.revocar_tokens(cuenta_id)
    assert verificador.handle(VerificarTokenQuery(token=access_token)) is None
    with pytest.raises(HTTPException) as revoked_error:
        asyncio.run(
            dependencies.obtener_usuario_actual(
                HTTPAuthorizationCredentials(scheme="Bearer", credentials=access_token)
            )
        )
    assert revoked_error.value.status_code == 401


def test_metricas_cuentan_enums_y_aliases_legacy(monkeypatch):
    Session = _sqlite_session(
        [PostulacionModel.__table__, HitoModel.__table__]
    )
    import app.infrastructure.metrica.repositories as repository_module

    monkeypatch.setattr(repository_module, "SessionLocal", Session)
    candidato_id = uuid4()
    estados = [
        EstadoPostulacionEnum.PENDIENTE,
        EstadoPostulacionEnum.ENTREVISTA,
        EstadoPostulacionEnum.ACEPTADO,
        EstadoPostulacionEnum.OFERTA,
        EstadoPostulacionEnum.RECHAZO,
    ]
    with Session() as db:
        for estado in estados:
            db.add(
                PostulacionModel(
                    postulacion_id=str(uuid4()),
                    cuenta_id=str(candidato_id),
                    puesto_id=str(uuid4()),
                    fecha_postulacion=datetime.now(),
                    estado=estado,
                    documentos_adjuntos=[],
                )
            )
        db.commit()

    registro = MetricaRepositoryImpl().obtener_por_postulante(
        candidato_id
    ).metrica_registro
    assert registro.total_postulaciones == 5
    assert registro.total_entrevistas == 1
    assert registro.total_exitos == 2
    assert registro.total_rechazos == 1
    assert registro.tasa_exito == 40


def test_empresa_solo_ve_perfil_de_postulantes_a_sus_vacantes(monkeypatch):
    Session = _sqlite_session(
        [
            CuentaModel.__table__,
            PuestoModel.__table__,
            RequisitoPuestoModel.__table__,
            PuestoMapeo.__table__,
            PostulacionModel.__table__,
            HitoModel.__table__,
        ]
    )
    monkeypatch.setattr(iam_router, "SessionLocal", Session)

    empresa_id = uuid4()
    otra_empresa_id = uuid4()
    candidato_id = uuid4()
    puesto_id = uuid4()
    with Session() as db:
        puesto = PuestoModel(
            titulo="Backend",
            empresa=str(empresa_id),
            descripcion="API",
            estado="abierto",
        )
        db.add(puesto)
        db.flush()
        db.add(PuestoMapeo(uuid_id=str(puesto_id), bd_id=puesto.id))
        db.add(
            PostulacionModel(
                postulacion_id=str(uuid4()),
                cuenta_id=str(candidato_id),
                puesto_id=str(puesto_id),
                fecha_postulacion=datetime.now(),
                estado=EstadoPostulacionEnum.PENDIENTE,
                documentos_adjuntos=[],
            )
        )
        db.commit()

    cuenta_data = {
        "cuenta_id": str(candidato_id),
        "rol": "postulante",
    }
    iam_router._validar_acceso_lectura_cuenta(
        cuenta_data,
        {"cuenta_id": str(empresa_id), "rol": "empresa"},
    )
    with pytest.raises(HTTPException) as error:
        iam_router._validar_acceso_lectura_cuenta(
            cuenta_data,
            {"cuenta_id": str(otra_empresa_id), "rol": "empresa"},
        )
    assert error.value.status_code == 403


def test_seed_demo_exige_confirmacion_y_bloquea_host_remoto(monkeypatch):
    import seed_demo

    monkeypatch.setattr(seed_demo.settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(
        seed_demo.settings,
        "DATABASE_URL",
        "postgresql://postgres:postgres@db.example.com/lookup",
    )

    with pytest.raises(SystemExit):
        seed_demo._validar_destino_reset(
            SimpleNamespace(confirm_reset=False, allow_remote_reset=False)
        )
    with pytest.raises(SystemExit):
        seed_demo._validar_destino_reset(
            SimpleNamespace(confirm_reset=True, allow_remote_reset=False)
        )
