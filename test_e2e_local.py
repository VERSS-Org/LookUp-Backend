"""Prueba end-to-end del backend LookUp local."""
import json
import sys
import time
import requests

BASE = "http://localhost:8000/api"
suffix = str(int(time.time()))
fails = []


def check(name, cond, detail=""):
    status = "OK " if cond else "FAIL"
    print(f"[{status}] {name} {detail if not cond else ''}")
    if not cond:
        fails.append(name)


# 1. Registro empresa
r = requests.post(f"{BASE}/iam/registrar", json={
    "nombre_completo": "TechCorp SAC",
    "email": f"empresa{suffix}@test.com",
    "password": "Empresa123!",
    "rol": "empresa",
})
check("registro empresa 201", r.status_code == 201, r.text)

# 1b. Registro admin debe fallar
r2 = requests.post(f"{BASE}/iam/registrar", json={
    "nombre_completo": "Hacker",
    "email": f"admin{suffix}@test.com",
    "password": "Admin1234!",
    "rol": "admin",
})
check("registro admin bloqueado 422", r2.status_code == 422, r2.text)

# 2. Login empresa
r = requests.post(f"{BASE}/iam/login", json={
    "email": f"empresa{suffix}@test.com", "password": "Empresa123!"})
check("login empresa 200", r.status_code == 200, r.text)
emp = r.json()
emp_h = {"Authorization": f"Bearer {emp['access_token']}"}

# 3. Crear puesto
r = requests.post(f"{BASE}/puesto/", headers=emp_h, json={
    "empresa_id": emp["cuenta_id"],
    "titulo": "Desarrollador Flutter",
    "descripcion": "Buscamos dev Flutter con experiencia en apps móviles y web.",
    "ubicacion": "Lima",
    "salario_min": 4000,
    "salario_max": 7000,
    "moneda": "PEN",
    "tipo_contrato": "tiempo_completo",
    "requisitos": [
        {"tipo": "experiencia", "descripcion": "2 años con Flutter", "es_obligatorio": True},
        {"tipo": "habilidad", "descripcion": "Ingles intermedio", "es_obligatorio": False},
    ],
})
check("crear puesto 201", r.status_code == 201, r.text)
puesto = r.json()
check("requisitos devueltos al crear", len(puesto.get("requisitos", [])) == 2, r.text)
r = requests.get(f"{BASE}/puesto/{puesto['puesto_id']}", headers=emp_h)
check("requisitos persisten al consultar", r.status_code == 200 and len(
    r.json().get("requisitos", [])) == 2, r.text)

# 3b. Salario invalido debe fallar
r2 = requests.post(f"{BASE}/puesto/", headers=emp_h, json={
    "empresa_id": emp["cuenta_id"], "titulo": "X", "descripcion": "Y",
    "ubicacion": "Lima", "salario_min": 5000, "salario_max": 1000,
    "tipo_contrato": "tiempo_completo",
})
check("puesto salario invalido 422", r2.status_code == 422, r2.text)

# 4. Registro + login postulante
r = requests.post(f"{BASE}/iam/registrar", json={
    "nombre_completo": "Juan Perez",
    "email": f"postulante{suffix}@test.com",
    "password": "Postula123!",
    "carrera": "Ing. Sistemas", "ciudad": "Lima",
    "rol": "postulante",
})
check("registro postulante 201", r.status_code == 201, r.text)
r = requests.post(f"{BASE}/iam/login", json={
    "email": f"postulante{suffix}@test.com", "password": "Postula123!"})
check("login postulante 200", r.status_code == 200, r.text)
pos = r.json()
pos_h = {"Authorization": f"Bearer {pos['access_token']}"}

# 5. Listar puestos como postulante (solo abiertos)
r = requests.get(f"{BASE}/puesto/?estado=abierto", headers=pos_h)
check("listar puestos postulante 200", r.status_code == 200 and any(
    p["puesto_id"] == puesto["puesto_id"] for p in r.json()), r.text)

# 6. Postular
r = requests.post(f"{BASE}/postulacion/", headers=pos_h, json={
    "candidato_id": pos["cuenta_id"], "puesto_id": puesto["puesto_id"],
    "documentos_adjuntos": []})
check("postular 201", r.status_code == 201, r.text)
postulacion = r.json()
check("postulacion enriquecida", "puesto" in postulacion and "empresa" in postulacion,
      json.dumps(postulacion)[:200])

# 6b. Postular duplicado debe fallar
r2 = requests.post(f"{BASE}/postulacion/", headers=pos_h, json={
    "candidato_id": pos["cuenta_id"], "puesto_id": puesto["puesto_id"]})
check("postulacion duplicada 400", r2.status_code == 400, r2.text)

# 7. Empresa lista candidatos del puesto
r = requests.get(f"{BASE}/postulacion/?puesto_id={puesto['puesto_id']}", headers=emp_h)
check("empresa lista candidatos 200", r.status_code == 200 and len(r.json()) == 1, r.text)

# 8. Cambiar estado a entrevista
r = requests.patch(
    f"{BASE}/postulacion/{postulacion['postulacion_id']}/estado",
    headers=emp_h, json={"nuevo_estado": "entrevista"})
check("estado -> entrevista 200", r.status_code == 200 and r.json()["estado"] == "entrevista", r.text)

# 8b. Postulante no puede cambiar estado
r2 = requests.patch(
    f"{BASE}/postulacion/{postulacion['postulacion_id']}/estado",
    headers=pos_h, json={"nuevo_estado": "oferta"})
check("postulante no cambia estado 403", r2.status_code == 403, r2.text)

# 9. Empresa envia feedback comentario
r = requests.post(f"{BASE}/contacto/feedback", headers=emp_h, json={
    "postulacion_id": postulacion["postulacion_id"],
    "empresa_id": emp["cuenta_id"],
    "cuenta_id": pos["cuenta_id"],
    "tipo_feedback": "comentario",
    "mensaje_texto": "Nos gusto tu perfil, te contactaremos.",
})
check("feedback comentario 201", r.status_code == 201, r.text)

# 10. Postulante responde mensaje
r = requests.post(f"{BASE}/contacto/mensaje", headers=pos_h, json={
    "postulacion_id": postulacion["postulacion_id"],
    "mensaje_texto": "Gracias, quedo atento.",
})
check("mensaje postulante 201", r.status_code == 201, r.text)

# 11. Listar contactos como postulante
r = requests.get(f"{BASE}/contacto/?postulacion_id={postulacion['postulacion_id']}", headers=pos_h)
check("listar contactos 200", r.status_code == 200 and len(r.json()) >= 2, r.text)

# 12. Feedback aprobacion -> estado aceptado
r = requests.post(f"{BASE}/contacto/feedback", headers=emp_h, json={
    "postulacion_id": postulacion["postulacion_id"],
    "empresa_id": emp["cuenta_id"],
    "cuenta_id": pos["cuenta_id"],
    "tipo_feedback": "aprobacion",
    "mensaje_texto": "Queremos hacerte una oferta.",
})
check("feedback aprobacion 201", r.status_code == 201, r.text)
r = requests.get(f"{BASE}/postulacion/{postulacion['postulacion_id']}", headers=pos_h)
check("estado tras aprobacion = aceptado", r.json().get("estado") == "aceptado", r.text[:200])

# 13. Metricas del postulante
r = requests.get(f"{BASE}/metricas/resumen/{pos['cuenta_id']}", headers=pos_h)
m = r.json()
check("metricas resumen", r.status_code == 200 and m["total_postulaciones"] == 1
      and m["total_exitos"] == 1, r.text)
r = requests.get(f"{BASE}/metricas/logros/{pos['cuenta_id']}", headers=pos_h)
check("logros incluyen Primera Aceptacion", r.status_code == 200 and any(
    logro["nombre_logro"] == "Primera Aceptación"
    for logro in r.json()), r.text)

# 14. Cuenta: PATCH y /me
r = requests.patch(f"{BASE}/iam/cuenta/{pos['cuenta_id']}", headers=pos_h,
                   json={"telefono": "+51 999 888 777"})
check("patch cuenta 200", r.status_code == 200 and r.json()["telefono"] == "+51 999 888 777", r.text)
r = requests.get(f"{BASE}/iam/me", headers=pos_h)
check("iam/me 200", r.status_code == 200 and r.json()["rol"] == "postulante", r.text)

# 15. Refresh token
r = requests.post(f"{BASE}/iam/refresh-token", json={"refresh_token": pos["refresh_token"]})
check("refresh token 200", r.status_code == 200 and r.json().get("access_token"), r.text)
nuevo_access = r.json().get("access_token")
r = requests.get(f"{BASE}/iam/me", headers={"Authorization": f"Bearer {nuevo_access}"})
check("access refrescado queda activo", r.status_code == 200, r.text)

# 16. Cerrar puesto
r = requests.patch(f"{BASE}/puesto/{puesto['puesto_id']}/estado", headers=emp_h,
                   json={"nuevo_estado": "cerrado"})
check("cerrar puesto 200", r.status_code == 200 and r.json()["estado"] == "cerrado", r.text)

# 16b. Postular a puesto cerrado debe fallar (con otro postulante)
requests.post(f"{BASE}/iam/registrar", json={
    "nombre_completo": "Maria Lopez", "email": f"maria{suffix}@test.com",
    "password": "Postula123!", "rol": "postulante"})
r2 = requests.post(f"{BASE}/iam/login", json={
    "email": f"maria{suffix}@test.com", "password": "Postula123!"})
maria = r2.json()
r2 = requests.post(f"{BASE}/postulacion/", headers={
    "Authorization": f"Bearer {maria['access_token']}"}, json={
    "candidato_id": maria["cuenta_id"], "puesto_id": puesto["puesto_id"]})
check("postular a cerrado 400", r2.status_code == 400, r2.text)

# 17. Seguridad: sin token
r = requests.get(f"{BASE}/puesto/")
check("listar puestos sin token 401/403", r.status_code in (401, 403), r.text)
r = requests.get(f"{BASE}/iam/cuenta/{pos['cuenta_id']}")
check("cuenta sin token bloqueada", r.status_code == 401, r.text)

print()
if fails:
    print(f"FALLARON {len(fails)}: {fails}")
    sys.exit(1)
print("TODOS LOS CHECKS PASARON")
