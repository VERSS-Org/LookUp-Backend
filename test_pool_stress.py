"""Valida que registro/login repetidos no agoten el pool de conexiones.

Reproduce el escenario del error `QueuePool limit of size 5 overflow 10
reached`: antes del fix, cada request autenticado filtraba una conexion
(CuentaRepositoryImpl abria una sesion en el constructor sin cerrarla),
por lo que ~15 requests bastaban para agotar el pool. Ejecutar con el
servidor corriendo en localhost:8000.
"""
import sys
import time
import requests

BASE = "http://localhost:8000/api"
N_CUENTAS = 8
LOGINS_POR_CUENTA = 4  # 8 registros + 32 logins + 40 /me = 80 requests > pool(15)

suffix = str(int(time.time()))
inicio = time.time()
fallos = []

for i in range(N_CUENTAS):
    email = f"stress{suffix}-{i}@test.com"
    r = requests.post(f"{BASE}/iam/registrar", json={
        "nombre_completo": f"Stress {i}",
        "email": email,
        "password": "Stress123!",
        "rol": "postulante",
    }, timeout=35)
    if r.status_code != 201:
        fallos.append(f"registro {i}: {r.status_code} {r.text[:120]}")
        continue

    for j in range(LOGINS_POR_CUENTA):
        r = requests.post(f"{BASE}/iam/login", json={
            "email": email, "password": "Stress123!"}, timeout=35)
        if r.status_code != 200:
            fallos.append(f"login {i}.{j}: {r.status_code} {r.text[:120]}")
            continue
        token = r.json()["access_token"]
        # /me usa la dependencia de autenticacion, que era la fuente del leak
        r = requests.get(f"{BASE}/iam/me", timeout=35,
                         headers={"Authorization": f"Bearer {token}"})
        if r.status_code != 200:
            fallos.append(f"me {i}.{j}: {r.status_code} {r.text[:120]}")

total = N_CUENTAS + N_CUENTAS * LOGINS_POR_CUENTA * 2
transcurrido = time.time() - inicio
print(f"{total} requests en {transcurrido:.1f}s, fallos: {len(fallos)}")
for f in fallos[:10]:
    print("  -", f)
sys.exit(1 if fallos else 0)
