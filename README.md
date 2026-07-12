# LookUp Backend

API FastAPI compartida por LookUp Postulantes y LookUp Empresas.

## Requisitos

- Python 3.10+
- PostgreSQL local o una base compatible (por ejemplo Supabase)

## Configuración

```powershell
cd LookUp-Backend-main
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
```

Edita `.env` con tus valores locales. No subas `.env` ni credenciales reales al repositorio.
Si sirves las apps web en otros puertos, agrégalos a `CORS_ORIGINS`.

## Ejecución local

```powershell
cd LookUp-Backend-main
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

La documentación interactiva queda en:

```text
http://localhost:8000/docs
```

Para Android Emulator, las apps Flutter deben apuntar a `http://10.0.2.2:8000`.
Para un teléfono físico, usa la IP LAN de la PC, por ejemplo `http://192.168.1.20:8000`.
Ambas apps aceptan `--dart-define=LOOKUP_API_BASE_URL=...` para cambiar la URL.

## Verificación

```powershell
pip install -r requirements-dev.txt
python -m compileall app
python -m ruff check app tests seed_demo.py test_e2e_local.py test_pool_stress.py
python -m pytest -q
```

Con el servidor corriendo, la prueba end-to-end valida el flujo completo de negocio
(registro, login, vacantes, postulaciones, estados, feedback, mensajes y métricas):

```powershell
.\.venv\Scripts\python.exe test_e2e_local.py
```

## Notas de seguridad

- El registro solo acepta los roles `postulante` y `empresa`; las cuentas `admin`
  no se crean por auto-servicio.
- Todos los endpoints de negocio requieren token JWT (`Authorization: Bearer ...`)
  y validan que la cuenta autenticada sea dueña del recurso.
