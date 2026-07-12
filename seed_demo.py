"""Limpia la base local y siembra datos de demostración realistas.

Uso (con el servidor corriendo en localhost:8000):
    .venv\\Scripts\\python.exe seed_demo.py --confirm-reset

Cuentas creadas (contraseña de todas: Demo123!):
    Empresas:    talento@bancodelsol.pe, rrhh@andinadigital.pe, personas@qhatu.pe
    Postulante:  carla.ramos@demo.pe
"""
import argparse
import sys

import requests
from sqlalchemy.engine import make_url

from app.config import settings

BASE = "http://localhost:8000/api"
PASSWORD = "Demo123!"
LOCAL_DATABASE_HOSTS = {None, "", "localhost", "127.0.0.1", "::1"}


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Reinicia una base local y crea datos demo de LookUp."
    )
    parser.add_argument(
        "--confirm-reset",
        action="store_true",
        help="Confirma que se eliminaran todos los datos de la base configurada.",
    )
    parser.add_argument(
        "--allow-remote-reset",
        action="store_true",
        help="Permite una base remota. Es peligroso y requiere --confirm-reset.",
    )
    return parser.parse_args()


def _validar_destino_reset(args) -> None:
    if settings.ENVIRONMENT != "development":
        raise SystemExit(
            "Abortado: seed_demo.py solo funciona con ENVIRONMENT=development."
        )
    if not args.confirm_reset:
        raise SystemExit(
            "Abortado: agrega --confirm-reset para autorizar el borrado total."
        )

    url = make_url(settings.DATABASE_URL)
    es_local = url.get_backend_name() == "sqlite" or url.host in LOCAL_DATABASE_HOSTS
    if not es_local and not args.allow_remote_reset:
        raise SystemExit(
            "Abortado: DATABASE_URL apunta a un host remoto. "
            "Usa una base local o confirma ademas --allow-remote-reset."
        )


def limpiar_base():
    from app.infrastructure.database.connection import SessionLocal
    from sqlalchemy import text

    db = SessionLocal()
    try:
        for tabla in [
            "feedbacks", "contactos_postulacion", "hitos", "postulaciones",
            "requisitos_puesto" if _tabla_existe(db, "requisitos_puesto") else None,
            "requisitos" if _tabla_existe(db, "requisitos") else None,
            "puesto_mapeo" if _tabla_existe(db, "puesto_mapeo") else None,
            "puestos", "tokens", "historial_accesos", "cuentas",
        ]:
            if tabla:
                db.execute(text(f"DELETE FROM {tabla}"))
        db.commit()
        print("Base de datos limpia.")
    finally:
        db.close()


def _tabla_existe(db, nombre):
    from sqlalchemy import inspect
    return nombre in inspect(db.get_bind()).get_table_names()


def registrar(nombre, email, rol, **extra):
    r = requests.post(f"{BASE}/iam/registrar", json={
        "nombre_completo": nombre, "email": email,
        "password": PASSWORD, "rol": rol, **extra,
    })
    r.raise_for_status()
    r = requests.post(f"{BASE}/iam/login",
                      json={"email": email, "password": PASSWORD})
    r.raise_for_status()
    data = r.json()
    return data["cuenta_id"], {"Authorization": f"Bearer {data['access_token']}"}


def main():
    limpiar_base()

    # ---- Empresas -----------------------------------------------------------
    empresas = {}
    for nombre, email, ciudad, descripcion in [
        ("Banco del Sol", "talento@bancodelsol.pe", "Lima",
         "Banco peruano con más de 20 años impulsando la inclusión financiera. "
         "Buscamos talento que quiera transformar la banca digital."),
        ("Andina Digital", "rrhh@andinadigital.pe", "Arequipa",
         "Agencia de producto digital: diseñamos y construimos aplicaciones "
         "web y móviles para clientes de todo el Perú."),
        ("Qhatu Marketplace", "personas@qhatu.pe", "Lima",
         "El marketplace que conecta a emprendedores peruanos con todo el "
         "país. Crecemos rápido y buscamos gente con iniciativa."),
    ]:
        cuenta_id, headers = registrar(nombre, email, "empresa", ciudad=ciudad)
        requests.patch(f"{BASE}/iam/cuenta/{cuenta_id}", headers=headers,
                       json={"perfil": {"descripcion": descripcion}})
        empresas[nombre] = (cuenta_id, headers)
        print(f"Empresa creada: {nombre} <{email}>")

    # ---- Vacantes -----------------------------------------------------------
    vacantes = [
        ("Banco del Sol", "Desarrollador/a Flutter Semi Senior",
         "Formarás parte del equipo de banca móvil, construyendo nuevas "
         "funcionalidades de la app con más de 2 millones de usuarios. "
         "Trabajo híbrido (3 días en oficina, San Isidro).",
         "San Isidro, Lima", 6500, 9000, "PEN", "tiempo_completo",
         [("experiencia", "2 años de experiencia con Flutter en producción", True),
          ("habilidad", "Consumo de APIs REST y manejo de estado", True),
          ("habilidad", "Inglés técnico para documentación", False)]),
        ("Banco del Sol", "Analista de Ciberseguridad",
         "Monitorearás y responderás a incidentes de seguridad, y apoyarás "
         "las auditorías internas del banco.",
         "San Isidro, Lima", 5500, 7500, "PEN", "tiempo_completo",
         [("experiencia", "1 año en SOC o respuesta a incidentes", True),
          ("certificacion", "Certificación en seguridad (deseable)", False)]),
        ("Andina Digital", "Diseñador/a UX/UI",
         "Diseñarás experiencias end-to-end para productos de clientes: "
         "research, wireframes, prototipos y sistemas de diseño en Figma.",
         "Arequipa", 3500, 5000, "PEN", "tiempo_completo",
         [("experiencia", "Portafolio con al menos 2 productos publicados", True),
          ("habilidad", "Dominio de Figma y prototipado", True),
          ("habilidad", "Conocimientos de accesibilidad", False)]),
        ("Andina Digital", "Desarrollador/a Backend Python",
         "Construirás APIs con FastAPI y PostgreSQL para productos de "
         "clientes. Trabajo 100% remoto desde cualquier ciudad del Perú.",
         "Remoto (Perú)", 1200, 1800, "USD", "tiempo_completo",
         [("experiencia", "2 años con Python en backend", True),
          ("habilidad", "FastAPI o Django, SQL y pruebas automatizadas", True)]),
        ("Andina Digital", "Practicante de Marketing Digital",
         "Apoyarás en campañas de redes sociales, métricas y contenido para "
         "las marcas de nuestros clientes. Convenio de prácticas.",
         "Arequipa", 1100, 1300, "PEN", "practicas",
         [("formacion", "Estudiante de Marketing o Comunicaciones", True)]),
        ("Qhatu Marketplace", "Product Manager",
         "Liderarás el descubrimiento y delivery del checkout y pagos. "
         "Trabajarás con diseño, ingeniería y datos.",
         "Miraflores, Lima", 9000, 13000, "PEN", "tiempo_completo",
         [("experiencia", "3 años como PM en productos digitales", True),
          ("habilidad", "Análisis de datos (SQL deseable)", False)]),
        ("Qhatu Marketplace", "Analista de Datos Junior",
         "Construirás dashboards y análisis para las áreas de crecimiento y "
         "operaciones. Stack: SQL, Python y Looker.",
         "Miraflores, Lima", 3000, 4200, "PEN", "tiempo_completo",
         [("habilidad", "SQL intermedio", True),
          ("habilidad", "Python para análisis (pandas)", False)]),
        ("Qhatu Marketplace", "Atención al Cliente Bilingüe (temporal)",
         "Atenderás a compradores y vendedores por chat y correo durante la "
         "campaña navideña (3 meses, posibilidad de renovar).",
         "Remoto (Perú)", 1800, 2200, "PEN", "temporal",
         [("habilidad", "Inglés intermedio-avanzado", True)]),
    ]

    puesto_ids = {}
    for empresa, titulo, descripcion, ubicacion, smin, smax, moneda, tipo, reqs in vacantes:
        cuenta_id, headers = empresas[empresa]
        r = requests.post(f"{BASE}/puesto/", headers=headers, json={
            "empresa_id": cuenta_id, "titulo": titulo,
            "descripcion": descripcion, "ubicacion": ubicacion,
            "salario_min": smin, "salario_max": smax, "moneda": moneda,
            "tipo_contrato": tipo,
            "requisitos": [
                {"tipo": t, "descripcion": d, "es_obligatorio": o}
                for t, d, o in reqs
            ],
        })
        r.raise_for_status()
        puesto_ids[titulo] = r.json()["puesto_id"]
        print(f"Vacante creada: {titulo} ({empresa})")

    # ---- Postulante demo ----------------------------------------------------
    carla_id, carla_h = registrar(
        "Carla Ramos Quispe", "carla.ramos@demo.pe", "postulante",
        carrera="Diseño UX", ciudad="Lima", telefono="+51 987 654 321",
    )
    requests.patch(f"{BASE}/iam/cuenta/{carla_id}", headers=carla_h, json={
        "perfil": {
            "descripcion": "Diseñadora UX con 3 años de experiencia en "
                           "productos digitales. Me apasiona la investigación "
                           "con usuarios y los sistemas de diseño.",
            "experiencia": [
                {"puesto": "Diseñadora UX", "organizacion": "Kunan Studio",
                 "periodo": "2023 - actualidad",
                 "descripcion": "Diseño de apps móviles para fintechs."},
                {"puesto": "Practicante de diseño", "organizacion": "Municipalidad de Lima",
                 "periodo": "2022", "descripcion": "Rediseño del portal de trámites."},
            ],
            "educacion": [
                {"titulo": "Bachiller en Diseño Gráfico",
                 "institucion": "PUCP", "periodo": "2017 - 2022"},
            ],
            "certificados": [
                {"nombre": "Google UX Design Certificate", "anio": "2023"},
            ],
            "habilidades": ["Figma", "Design Systems", "UX Research",
                            "Prototipado", "HTML/CSS básico"],
            "idiomas": [
                {"idioma": "Español", "nivel": "Nativo"},
                {"idioma": "Inglés", "nivel": "Intermedio"},
            ],
            "extras": [
                {"titulo": "Proyecto personal: app de trueque Trueke",
                 "descripcion": "Diseño end-to-end publicado en Behance."},
            ],
        },
    })
    print("Postulante demo: Carla Ramos <carla.ramos@demo.pe>")

    # ---- Postulaciones + conversaciones -------------------------------------
    def postular(titulo):
        r = requests.post(f"{BASE}/postulacion/", headers=carla_h, json={
            "candidato_id": carla_id, "puesto_id": puesto_ids[titulo]})
        r.raise_for_status()
        return r.json()["postulacion_id"]

    # 1) UX/UI en Andina Digital: en revisión + mensajes (no leídos para Carla)
    p1 = postular("Diseñador/a UX/UI")
    _, andina_h = empresas["Andina Digital"]
    requests.patch(f"{BASE}/postulacion/{p1}/estado", headers=andina_h,
                   json={"nuevo_estado": "en_revision"})
    requests.post(f"{BASE}/contacto/feedback", headers=andina_h, json={
        "postulacion_id": p1, "empresa_id": empresas["Andina Digital"][0],
        "cuenta_id": carla_id, "tipo_feedback": "comentario",
        "mensaje_texto": "Hola Carla, nos gustó tu portafolio. ¿Tienes "
                         "disponibilidad para una llamada esta semana?"})

    # 2) Analista de Datos en Qhatu: entrevista, con conversación completa
    p2 = postular("Analista de Datos Junior")
    _, qhatu_h = empresas["Qhatu Marketplace"]
    requests.patch(f"{BASE}/postulacion/{p2}/estado", headers=qhatu_h,
                   json={"nuevo_estado": "en_revision"})
    requests.post(f"{BASE}/contacto/feedback", headers=qhatu_h, json={
        "postulacion_id": p2, "empresa_id": empresas["Qhatu Marketplace"][0],
        "cuenta_id": carla_id, "tipo_feedback": "comentario",
        "mensaje_texto": "Hola Carla, gracias por postular. Revisamos tu CV y "
                         "queremos conocerte."})
    requests.post(f"{BASE}/contacto/mensaje", headers=carla_h, json={
        "postulacion_id": p2,
        "mensaje_texto": "¡Gracias! Quedo atenta a la coordinación."})
    requests.patch(f"{BASE}/postulacion/{p2}/estado", headers=qhatu_h,
                   json={"nuevo_estado": "entrevista"})
    requests.post(f"{BASE}/contacto/feedback", headers=qhatu_h, json={
        "postulacion_id": p2, "empresa_id": empresas["Qhatu Marketplace"][0],
        "cuenta_id": carla_id, "tipo_feedback": "comentario",
        "mensaje_texto": "Te agendamos entrevista el jueves a las 10:00 a.m. "
                         "por Google Meet. ¡Éxitos!"})

    # 3) Flutter en Banco del Sol: pendiente (recién enviada)
    postular("Desarrollador/a Flutter Semi Senior")

    print("\nListo. Cuentas demo (contraseña Demo123!):")
    print("  Postulante: carla.ramos@demo.pe")
    print("  Empresas:   talento@bancodelsol.pe · rrhh@andinadigital.pe · personas@qhatu.pe")


if __name__ == "__main__":
    argumentos = _parse_args()
    _validar_destino_reset(argumentos)
    try:
        requests.get(f"{BASE.rsplit('/', 1)[0]}/", timeout=5)
    except Exception:
        print("El backend no está corriendo en localhost:8000.")
        sys.exit(1)
    main()
