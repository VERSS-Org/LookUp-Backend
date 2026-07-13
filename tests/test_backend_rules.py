import asyncio
import json
from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.domain.common import AggregateRoot, Event
from app.domain.iam.entities import EstadoCuentaEnum, RolEnum
from app.application.iam.query_handlers import (
    VerificarTokenQuery,
    VerificarTokenQueryHandler,
)
from app.application.iam.command_handlers import CrearCuentaCommand, CrearCuentaHandler
from app.application.puesto.command_handlers import (
    ActualizarPuestoCommand,
    ActualizarPuestoHandler,
    CrearPuestoCommand,
    CrearPuestoHandler,
)
from app.domain.iam.entities import Cuenta, CuentaAggregate
from app.infrastructure.metrica.repositories import MetricaRepositoryImpl
from app.domain.postulacion.entities import (
    EstadoPostulacion,
    EstadoPostulacionEnum,
    LineaDeTiempo,
    Postulacion,
    PostulacionAggregate,
)
from app.domain.puesto.entities import (
    Puesto,
    PuestoAggregate,
    Requisito,
    TipoContratoEnum,
)
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
from app.interface.api.iam.schemas import CrearCuentaRequest, CuentaUpdateRequest
from app.interface.api.postulacion import router as postulacion_router
from app.interface.api.puesto import router as puesto_router


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


def test_postulacion_endpoint_expone_hitos_estructurados(monkeypatch):
    pendiente = EstadoPostulacion(EstadoPostulacionEnum.PENDIENTE)
    aggregate = PostulacionAggregate(
        postulacion=Postulacion(
            candidato_id=uuid4(),
            puesto_id=uuid4(),
            estado=pendiente,
        ),
        estado=pendiente,
        linea_de_tiempo=LineaDeTiempo(),
    )

    aggregate.postularse()
    assert aggregate.cambiar_estado("en_revision")

    class Repositorio:
        @staticmethod
        def obtener_por_id(_postulacion_id):
            return aggregate

    monkeypatch.setattr(
        postulacion_router, "PostulacionRepositoryImpl", Repositorio
    )
    monkeypatch.setattr(
        postulacion_router.postulacion_service,
        "enriquecer_postulacion",
        lambda postulacion, **_kwargs: postulacion,
    )
    app = FastAPI()
    app.include_router(postulacion_router.router, prefix="/api")
    app.dependency_overrides[dependencies.obtener_usuario_actual] = lambda: {
        "cuenta_id": str(aggregate.postulacion.candidato_id),
        "rol": "postulante",
    }

    response = TestClient(app).get(
        f"/api/postulacion/{aggregate.postulacion.postulacion_id}"
    )

    assert response.status_code == 200, response.text
    hitos = response.json()["hitos"]
    assert hitos[0]["tipo_evento"] == "postulacion_creada"
    assert hitos[0]["estado_nuevo"] == "pendiente"
    assert hitos[1]["tipo_evento"] == "estado_actualizado"
    assert hitos[1]["estado_anterior"] == "pendiente"
    assert hitos[1]["estado_nuevo"] == "en_revision"
    assert "en_revision" in hitos[1]["descripcion"]


def test_eventos_endpoint_estructura_hitos_legacy(monkeypatch):
    Session = _sqlite_session(
        [
            PuestoModel.__table__,
            RequisitoPuestoModel.__table__,
            PuestoMapeo.__table__,
            PostulacionModel.__table__,
            HitoModel.__table__,
        ]
    )
    monkeypatch.setattr(postulacion_router, "SessionLocal", Session)
    candidato_id = uuid4()
    puesto_id = uuid4()
    postulacion_id = uuid4()
    with Session() as db:
        puesto = PuestoModel(
            titulo="Backend",
            empresa=str(uuid4()),
            descripcion="API",
            estado="abierto",
        )
        db.add(puesto)
        db.flush()
        db.add(PuestoMapeo(uuid_id=str(puesto_id), bd_id=puesto.id))
        postulacion = PostulacionModel(
            postulacion_id=str(postulacion_id),
            cuenta_id=str(candidato_id),
            puesto_id=str(puesto_id),
            fecha_postulacion=datetime.now(),
            estado=EstadoPostulacionEnum.ENTREVISTA,
            documentos_adjuntos=[],
        )
        db.add(postulacion)
        db.flush()
        db.add(
            HitoModel(
                postulacion_id=postulacion.id,
                fecha=datetime.now(),
                descripcion=(
                    "Estado actualizado de en_revision a entrevista"
                ),
            )
        )
        db.commit()

    app = FastAPI()
    app.include_router(postulacion_router.router, prefix="/api")
    app.dependency_overrides[dependencies.obtener_usuario_actual] = lambda: {
        "cuenta_id": str(candidato_id),
        "rol": "postulante",
    }

    response = TestClient(app).get("/api/postulacion/eventos")

    assert response.status_code == 200, response.text
    assert response.json() == [
        {
            "tipo": "hito",
            "tipo_evento": "estado_actualizado",
            "titulo": "Backend",
            "descripcion": "Estado actualizado de en_revision a entrevista",
            "fecha": response.json()[0]["fecha"],
            "postulacion_id": str(postulacion_id),
            "estado_anterior": "en_revision",
            "estado_nuevo": "entrevista",
        }
    ]


def test_tokens_generados_son_unicos_y_el_historial_usa_datetime():
    datos = {"sub": str(uuid4()), "tipo": "access"}
    assert TokenManager.crear_access_token(datos) != TokenManager.crear_access_token(
        datos
    )

    aggregate = CuentaAggregate(cuenta=Cuenta())
    aggregate.aplicar_login_exitoso()
    assert isinstance(aggregate.historial_accesos[0]["fecha"], datetime)


def test_carrera_se_normaliza_al_registrar_y_actualizar_perfil():
    registro = CrearCuentaRequest(
        nombre_completo="Luis Rodriguez",
        email="luis@example.com",
        password="Clave123!",
        carrera="  Ingenieria de Software  ",
    )
    actualizacion = CuentaUpdateRequest(carrera="  Ingenieria de Software  ")
    carrera_vacia = CuentaUpdateRequest(carrera="   ")

    assert registro.carrera == "Ingenieria de Software"
    assert actualizacion.carrera == "Ingenieria de Software"
    assert carrera_vacia.carrera is None


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
    assert repository.aggregate.cuenta.perfil == {"mostrar_email": True}


def test_preferencia_de_email_exige_booleano():
    assert CuentaUpdateRequest(
        perfil={"mostrar_email": False}
    ).perfil == {"mostrar_email": False}

    with pytest.raises(ValueError):
        CuentaUpdateRequest(perfil={"mostrar_email": "false"})


def test_empresa_actualiza_telefono_y_ciudad_por_endpoint(monkeypatch):
    Session = _sqlite_session(
        [
            CuentaModel.__table__,
            TokenModel.__table__,
            HistorialAccesoModel.__table__,
        ]
    )
    import app.infrastructure.iam.repositories as repository_module

    monkeypatch.setattr(repository_module, "SessionLocal", Session)
    cuenta_id = uuid4()
    with Session() as db:
        db.add(
            CuentaModel(
                id=cuenta_id,
                email="empresa@example.com",
                hash_password="hash",
                nombre_completo="Empresa Demo",
                rol=RolEnum.EMPRESA,
                estado=EstadoCuentaEnum.ACTIVA,
                fecha_creacion=datetime.now(),
            )
        )
        db.commit()

    app = FastAPI()
    app.include_router(iam_router.router, prefix="/api")
    app.dependency_overrides[dependencies.obtener_usuario_actual] = lambda: {
        "cuenta_id": str(cuenta_id),
        "rol": "empresa",
    }

    response = TestClient(app).patch(
        f"/api/iam/cuenta/{cuenta_id}",
        json={"telefono": "  +51 999 888 777  ", "ciudad": "  Lima  "},
    )

    assert response.status_code == 200, response.text
    assert response.json()["telefono"] == "+51 999 888 777"
    assert response.json()["ciudad"] == "Lima"
    with Session() as db:
        cuenta = db.get(CuentaModel, cuenta_id)
        assert cuenta.telefono == "+51 999 888 777"
        assert cuenta.ciudad == "Lima"


def test_compatibilidad_agrega_contacto_a_esquema_legacy(monkeypatch):
    import app.main as main_module

    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE cuentas (id VARCHAR PRIMARY KEY)"))

    monkeypatch.setattr(main_module, "engine", engine)
    main_module._ensure_runtime_schema()

    columnas = {columna["name"] for columna in inspect(engine).get_columns("cuentas")}
    assert {"telefono", "ciudad"}.issubset(columnas)


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


def test_api_rechaza_freelance_al_crear_y_actualizar_vacantes():
    empresa_id = uuid4()
    app = FastAPI()
    app.include_router(puesto_router.router, prefix="/api")
    app.dependency_overrides[dependencies.obtener_usuario_actual] = lambda: {
        "cuenta_id": str(empresa_id),
        "rol": "empresa",
    }
    client = TestClient(app)

    create_response = client.post(
        "/api/puesto/",
        json={
            "empresa_id": str(empresa_id),
            "titulo": "Backend",
            "descripcion": "Desarrollo de API",
            "ubicacion": "Lima",
            "tipo_contrato": "freelance",
        },
    )
    update_response = client.put(
        f"/api/puesto/{uuid4()}",
        json={"tipo_contrato": "freelance"},
    )

    assert create_response.status_code == 422
    assert update_response.status_code == 422
    assert "freelance" in create_response.text
    assert "freelance" in update_response.text


def test_regla_de_dominio_no_persiste_freelance_en_nuevas_escrituras():
    class Repositorio:
        def __init__(self):
            self.guardados = 0
            self.aggregate = PuestoAggregate(
                puesto=Puesto(
                    empresa_id=uuid4(),
                    titulo="Backend",
                    descripcion="API",
                )
            )

        def obtener_por_id(self, _puesto_id):
            return self.aggregate

        def guardar(self, aggregate):
            self.guardados += 1
            return aggregate.puesto.puesto_id

    repository = Repositorio()
    with pytest.raises(ValueError, match="no está permitido"):
        CrearPuestoHandler(repository).handle(
            CrearPuestoCommand(
                empresa_id=uuid4(),
                titulo="Proyecto",
                descripcion="Trabajo por proyecto",
                ubicacion="Remoto",
                tipo_contrato=TipoContratoEnum.FREELANCE,
            )
        )
    with pytest.raises(ValueError, match="no está permitido"):
        ActualizarPuestoHandler(repository).handle(
            ActualizarPuestoCommand(
                puesto_id=repository.aggregate.puesto.puesto_id,
                tipo_contrato=TipoContratoEnum.FREELANCE,
            )
        )

    assert repository.guardados == 0


def test_repositorio_lee_tipo_freelance_legacy(monkeypatch):
    Session = _sqlite_session(
        [
            PuestoModel.__table__,
            RequisitoPuestoModel.__table__,
            PuestoMapeo.__table__,
        ]
    )
    import app.infrastructure.puesto.repositories as repository_module

    monkeypatch.setattr(repository_module, "SessionLocal", Session)
    puesto_id = uuid4()
    with Session() as db:
        puesto = PuestoModel(
            titulo="Proyecto heredado",
            empresa=str(uuid4()),
            descripcion="Registro anterior al catalogo actual",
            ubicacion="Remoto",
            tipo_contrato="freelance",
            estado="abierto",
        )
        db.add(puesto)
        db.flush()
        db.add(PuestoMapeo(uuid_id=str(puesto_id), bd_id=puesto.id))
        db.commit()

    recuperado = PuestoRepositoryImpl().obtener_por_id(puesto_id)

    assert recuperado is not None
    assert recuperado.puesto.tipo_contrato == TipoContratoEnum.FREELANCE


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


def _insertar_escenario_privacidad_email(Session, perfil_candidato):
    empresa_id = uuid4()
    candidato_id = uuid4()
    puesto_id = uuid4()
    postulacion_id = uuid4()
    with Session() as db:
        db.add_all([
            CuentaModel(
                id=empresa_id,
                email="empresa@example.com",
                hash_password="hash",
                nombre_completo="Empresa Demo",
                rol=RolEnum.EMPRESA,
                estado=EstadoCuentaEnum.ACTIVA,
                activa=True,
                fecha_creacion=datetime.now(),
            ),
            CuentaModel(
                id=candidato_id,
                email="postulante@example.com",
                hash_password="hash",
                nombre_completo="Postulante Demo",
                perfil=json.dumps(perfil_candidato),
                rol=RolEnum.POSTULANTE,
                estado=EstadoCuentaEnum.ACTIVA,
                activa=True,
                fecha_creacion=datetime.now(),
            ),
        ])
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
                postulacion_id=str(postulacion_id),
                cuenta_id=str(candidato_id),
                puesto_id=str(puesto_id),
                fecha_postulacion=datetime.now(),
                estado=EstadoPostulacionEnum.PENDIENTE,
                documentos_adjuntos=[],
            )
        )
        db.commit()
    return empresa_id, candidato_id, puesto_id, postulacion_id


def test_preferencia_email_se_guarda_y_protege_perfiles_autorizados(monkeypatch):
    Session = _sqlite_session(
        [
            CuentaModel.__table__,
            TokenModel.__table__,
            HistorialAccesoModel.__table__,
            PuestoModel.__table__,
            RequisitoPuestoModel.__table__,
            PuestoMapeo.__table__,
            PostulacionModel.__table__,
            HitoModel.__table__,
        ]
    )
    import app.infrastructure.iam.repositories as iam_repository_module

    monkeypatch.setattr(iam_repository_module, "SessionLocal", Session)
    monkeypatch.setattr(iam_router, "SessionLocal", Session)
    empresa_id, candidato_id, _, _ = _insertar_escenario_privacidad_email(
        Session,
        {"descripcion": "Perfil legado"},
    )

    usuario = {
        "cuenta_id": str(empresa_id),
        "rol": "empresa",
    }
    app = FastAPI()
    app.include_router(iam_router.router, prefix="/api")
    app.dependency_overrides[dependencies.obtener_usuario_actual] = lambda: usuario
    client = TestClient(app)

    # Compatibilidad: un perfil anterior a la preferencia sigue siendo visible.
    response = client.get(f"/api/iam/cuenta/{candidato_id}")
    assert response.status_code == 200, response.text
    assert response.json()["email"] == "postulante@example.com"

    # El postulante guarda solo la preferencia sin perder el resto del perfil.
    usuario.update({"cuenta_id": str(candidato_id), "rol": "postulante"})
    response = client.patch(
        f"/api/iam/cuenta/{candidato_id}",
        json={"perfil": {"mostrar_email": False}},
    )
    assert response.status_code == 200, response.text
    assert response.json()["email"] == "postulante@example.com"
    assert response.json()["perfil"] == {
        "descripcion": "Perfil legado",
        "mostrar_email": False,
    }

    # La empresa autorizada ya no lo obtiene por ID ni por la ruta por correo.
    usuario.update({"cuenta_id": str(empresa_id), "rol": "empresa"})
    response = client.get(f"/api/iam/cuenta/{candidato_id}")
    assert response.status_code == 200, response.text
    assert response.json()["email"] is None
    response = client.get("/api/iam/cuenta/email/postulante@example.com")
    assert response.status_code == 200, response.text
    assert response.json()["email"] is None

    # La privacidad nunca oculta las credenciales al titular autenticado.
    usuario.update({"cuenta_id": str(candidato_id), "rol": "postulante"})
    response = client.get(f"/api/iam/cuenta/{candidato_id}")
    assert response.status_code == 200, response.text
    assert response.json()["email"] == "postulante@example.com"
    response = client.get("/api/iam/me")
    assert response.status_code == 200, response.text
    assert response.json()["email"] == "postulante@example.com"

    # La decisión es reversible: al volver a mostrarlo, la empresa lo recibe.
    response = client.patch(
        f"/api/iam/cuenta/{candidato_id}",
        json={"perfil": {"mostrar_email": True}},
    )
    assert response.status_code == 200, response.text
    usuario.update({"cuenta_id": str(empresa_id), "rol": "empresa"})
    response = client.get(f"/api/iam/cuenta/{candidato_id}")
    assert response.status_code == 200, response.text
    assert response.json()["email"] == "postulante@example.com"


def test_postulaciones_no_filtran_email_oculto_a_la_empresa(monkeypatch):
    Session = _sqlite_session(
        [
            CuentaModel.__table__,
            TokenModel.__table__,
            HistorialAccesoModel.__table__,
            PuestoModel.__table__,
            RequisitoPuestoModel.__table__,
            PuestoMapeo.__table__,
            PostulacionModel.__table__,
            HitoModel.__table__,
        ]
    )
    import app.infrastructure.iam.repositories as iam_repository_module
    import app.infrastructure.postulacion.repositories as postulacion_repository_module
    import app.infrastructure.puesto.repositories as puesto_repository_module

    monkeypatch.setattr(iam_repository_module, "SessionLocal", Session)
    monkeypatch.setattr(postulacion_repository_module, "SessionLocal", Session)
    monkeypatch.setattr(puesto_repository_module, "SessionLocal", Session)
    empresa_id, candidato_id, puesto_id, postulacion_id = (
        _insertar_escenario_privacidad_email(
            Session,
            {"mostrar_email": False},
        )
    )

    usuario = {"cuenta_id": str(empresa_id), "rol": "empresa"}
    app = FastAPI()
    app.include_router(postulacion_router.router, prefix="/api")
    app.dependency_overrides[dependencies.obtener_usuario_actual] = lambda: usuario
    client = TestClient(app)

    response = client.get(f"/api/postulacion/{postulacion_id}")
    assert response.status_code == 200, response.text
    assert response.json()["candidato"]["email"] is None

    response = client.get(f"/api/postulacion/?puesto_id={puesto_id}")
    assert response.status_code == 200, response.text
    assert response.json()[0]["candidato"]["email"] is None

    response = client.patch(
        f"/api/postulacion/{postulacion_id}/estado",
        json={"nuevo_estado": "en_revision"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["candidato"]["email"] is None

    usuario.update({"cuenta_id": str(candidato_id), "rol": "postulante"})
    response = client.get(f"/api/postulacion/{postulacion_id}")
    assert response.status_code == 200, response.text
    assert response.json()["candidato"]["email"] == "postulante@example.com"

    response = client.get(f"/api/postulacion/?candidato_id={candidato_id}")
    assert response.status_code == 200, response.text
    assert response.json()[0]["candidato"]["email"] == "postulante@example.com"


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
