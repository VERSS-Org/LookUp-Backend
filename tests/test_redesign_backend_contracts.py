from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.domain.iam.entities import EstadoCuentaEnum, RolEnum
from app.domain.postulacion.entities import EstadoPostulacionEnum
from app.infrastructure.contacto.models import (
    ContactoPostulacionModel,
    FeedbackModel,
)
from app.infrastructure.database.connection import Base
from app.infrastructure.iam.models import CuentaModel
from app.infrastructure.postulacion.models import HitoModel, PostulacionModel
from app.infrastructure.puesto.models import PuestoMapeo, PuestoModel
from app.interface.api import dependencies
from app.interface.api.contacto import router as contacto_router
from app.interface.api.metrica import router as metrica_router
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


def _cuenta(cuenta_id, rol, nombre):
    return CuentaModel(
        id=cuenta_id,
        email=f"{cuenta_id}@example.com",
        hash_password="hash",
        nombre_completo=nombre,
        rol=rol,
        estado=EstadoCuentaEnum.ACTIVA,
        fecha_creacion=datetime.now(),
        activa=True,
    )


def test_vacantes_resuelven_empresa_con_ids_serializados(monkeypatch):
    Session = _sqlite_session([CuentaModel.__table__])
    monkeypatch.setattr(puesto_router, "SessionLocal", Session)
    empresa_id = uuid4()
    with Session() as db:
        db.add(_cuenta(empresa_id, RolEnum.EMPRESA, "Nexa Analytics"))
        db.commit()

    resultado = puesto_router._empresas_info({str(empresa_id)})

    assert resultado == {str(empresa_id): {"nombre": "Nexa Analytics", "foto": None}}


def test_bandeja_separa_conversaciones_por_postulacion_exacta(monkeypatch):
    Session = _sqlite_session(
        [
            CuentaModel.__table__,
            PuestoModel.__table__,
            PuestoMapeo.__table__,
            PostulacionModel.__table__,
            HitoModel.__table__,
            ContactoPostulacionModel.__table__,
            FeedbackModel.__table__,
        ]
    )
    monkeypatch.setattr(contacto_router, "SessionLocal", Session)
    empresa_id = uuid4()
    candidato_id = uuid4()
    puesto_ids = [uuid4(), uuid4()]
    postulacion_ids = [uuid4(), uuid4()]
    contacto_ids = [uuid4(), uuid4()]

    with Session() as db:
        db.add_all(
            [
                _cuenta(empresa_id, RolEnum.EMPRESA, "Nexa Analytics"),
                _cuenta(candidato_id, RolEnum.POSTULANTE, "Valeria Campos"),
            ]
        )
        for index, puesto_id in enumerate(puesto_ids):
            puesto = PuestoModel(
                titulo=f"Vacante {index + 1}",
                empresa=str(empresa_id),
                descripcion="Descripcion",
                estado="abierto",
            )
            db.add(puesto)
            db.flush()
            db.add(PuestoMapeo(uuid_id=str(puesto_id), bd_id=puesto.id))
            db.add(
                PostulacionModel(
                    postulacion_id=str(postulacion_ids[index]),
                    cuenta_id=str(candidato_id),
                    puesto_id=str(puesto_id),
                    fecha_postulacion=datetime.now(),
                    estado=EstadoPostulacionEnum.EN_REVISION,
                    documentos_adjuntos=[],
                )
            )
            db.add(
                ContactoPostulacionModel(
                    id=str(contacto_ids[index]),
                    postulacion_id=str(postulacion_ids[index]),
                    empresa_id=str(empresa_id),
                    cuenta_id=str(candidato_id),
                    tipo_mensaje="actualizacion",
                    remitente_rol="postulante",
                    fecha_hora=datetime.now() + timedelta(minutes=index),
                    leido=False,
                )
            )
            db.add(
                FeedbackModel(
                    contacto_id=str(contacto_ids[index]),
                    tipo="otro",
                    mensaje_texto=f"Mensaje {index + 1}",
                )
            )
        db.commit()

    app = FastAPI()
    app.include_router(contacto_router.router, prefix="/api")
    app.dependency_overrides[dependencies.obtener_usuario_actual] = lambda: {
        "cuenta_id": str(empresa_id),
        "rol": "empresa",
    }

    response = TestClient(app).get("/api/contacto/bandeja")

    assert response.status_code == 200, response.text
    hilos = response.json()
    assert {hilo["postulacion_id"] for hilo in hilos} == {
        str(postulacion_id) for postulacion_id in postulacion_ids
    }
    assert {hilo["puesto_titulo"] for hilo in hilos} == {
        "Vacante 1",
        "Vacante 2",
    }
    assert all(
        hilo["contraparte"]
        == {
            "cuenta_id": str(candidato_id),
            "nombre": "Valeria Campos",
            "foto_url": None,
        }
        for hilo in hilos
    )


def test_novedades_de_empresa_resuelven_nombre_del_postulante(monkeypatch):
    Session = _sqlite_session(
        [
            CuentaModel.__table__,
            PuestoModel.__table__,
            PuestoMapeo.__table__,
            PostulacionModel.__table__,
            HitoModel.__table__,
        ]
    )
    monkeypatch.setattr(postulacion_router, "SessionLocal", Session)
    empresa_id = uuid4()
    candidato_id = uuid4()
    puesto_id = uuid4()
    postulacion_id = uuid4()

    with Session() as db:
        db.add(_cuenta(candidato_id, RolEnum.POSTULANTE, "Valeria Campos"))
        puesto = PuestoModel(
            titulo="Analista de Datos Jr.",
            empresa=str(empresa_id),
            descripcion="Descripcion",
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

    app = FastAPI()
    app.include_router(postulacion_router.router, prefix="/api")
    app.dependency_overrides[dependencies.obtener_usuario_actual] = lambda: {
        "cuenta_id": str(empresa_id),
        "rol": "empresa",
    }

    response = TestClient(app).get("/api/postulacion/eventos")

    assert response.status_code == 200, response.text
    assert response.json()[0]["descripcion"] == "Valeria Campos"
    assert response.json()[0]["postulacion_id"] == str(postulacion_id)


def test_progreso_usa_embudo_historico_y_logros_estables(monkeypatch):
    Session = _sqlite_session([PostulacionModel.__table__, HitoModel.__table__])
    import app.infrastructure.metrica.repositories as repository_module

    monkeypatch.setattr(repository_module, "SessionLocal", Session)
    candidato_id = uuid4()
    inicio = datetime(2026, 7, 2, 9)
    estados = [
        EstadoPostulacionEnum.ACEPTADO,
        EstadoPostulacionEnum.RECHAZADO,
        EstadoPostulacionEnum.EN_REVISION,
        EstadoPostulacionEnum.PENDIENTE,
        EstadoPostulacionEnum.ENTREVISTA,
    ]

    with Session() as db:
        postulaciones = []
        for index, estado in enumerate(estados):
            postulacion = PostulacionModel(
                postulacion_id=str(uuid4()),
                cuenta_id=str(candidato_id),
                puesto_id=str(uuid4()),
                fecha_postulacion=inicio + timedelta(days=index),
                estado=estado,
                documentos_adjuntos=[],
            )
            db.add(postulacion)
            db.flush()
            postulaciones.append(postulacion)

        db.add_all(
            [
                HitoModel(
                    postulacion_id=postulaciones[0].id,
                    fecha=inicio + timedelta(hours=2),
                    descripcion="Estado actualizado de pendiente a en_revision",
                    tipo_evento="estado_actualizado",
                    estado_anterior="pendiente",
                    estado_nuevo="en_revision",
                ),
                HitoModel(
                    postulacion_id=postulaciones[0].id,
                    fecha=inicio + timedelta(days=1, hours=2),
                    descripcion="Estado actualizado de en_revision a entrevista",
                    tipo_evento="estado_actualizado",
                    estado_anterior="en_revision",
                    estado_nuevo="entrevista",
                ),
                HitoModel(
                    postulacion_id=postulaciones[1].id,
                    fecha=inicio + timedelta(days=1, hours=3),
                    descripcion="Estado actualizado de pendiente a en_revision",
                    tipo_evento="estado_actualizado",
                    estado_anterior="pendiente",
                    estado_nuevo="en_revision",
                ),
            ]
        )
        db.commit()

    app = FastAPI()
    app.include_router(metrica_router.router, prefix="/api")
    app.dependency_overrides[dependencies.obtener_usuario_actual] = lambda: {
        "cuenta_id": str(candidato_id),
        "rol": "postulante",
    }
    client = TestClient(app)

    resumen = client.get(f"/api/metricas/resumen/{candidato_id}")
    primera_lectura = client.get(f"/api/metricas/logros/{candidato_id}")
    segunda_lectura = client.get(f"/api/metricas/logros/{candidato_id}")

    assert resumen.status_code == 200, resumen.text
    assert resumen.json() == {
        "cuenta_id": str(candidato_id),
        "total_postulaciones": 5,
        "total_en_revision": 3,
        "total_entrevistas": 2,
        "total_exitos": 1,
        "total_rechazos": 1,
        "tasa_exito": 20.0,
    }
    assert primera_lectura.status_code == 200, primera_lectura.text
    assert primera_lectura.json() == segunda_lectura.json()
    assert [logro["nombre_logro"] for logro in primera_lectura.json()] == [
        "Primera postulación",
        "5 postulaciones enviadas",
        "Primera entrevista",
    ]
    assert [logro["fecha_obtencion"] for logro in primera_lectura.json()] == [
        inicio.isoformat(),
        (inicio + timedelta(days=4)).isoformat(),
        (inicio + timedelta(days=1, hours=2)).isoformat(),
    ]
