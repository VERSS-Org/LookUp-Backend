# LookUp Backend

API FastAPI compartida por LookUp User y LookUp Recruiter.

## Requisitos

- Python 3.10+
- PostgreSQL local o una base compatible (por ejemplo Supabase)

## Configuracion

```powershell
cd C:\Users\luisp\Downloads\LookUp\LookUp-Backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
```

Edita `.env` con tus valores locales. No subas `.env` ni credenciales reales al repositorio.

## Ejecucion local

```powershell
cd C:\Users\luisp\Downloads\LookUp\LookUp-Backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

La documentacion interactiva queda en:

```text
http://localhost:8000/docs
```

Para Android Emulator, las apps Flutter deben apuntar a `http://10.0.2.2:8000`.
Para un telefono fisico, usa la IP LAN de la PC, por ejemplo `http://192.168.1.20:8000`.

## Verificacion

```powershell
python -m compileall app
```
