from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from datetime import datetime

from app.infrastructure.iam.security import TokenManager
from app.infrastructure.iam.repositories import CuentaRepositoryImpl
from app.infrastructure.iam.models import TokenModel
from app.infrastructure.database.connection import SessionLocal
from app.application.iam.query_handlers import ObtenerCuentaQueryHandler, ObtenerCuentaQuery
from uuid import UUID

security = HTTPBearer(auto_error=False)


async def obtener_usuario_actual(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """
    Dependencia para obtener el usuario actual a partir del token JWT.
    
    Uso:
    @router.get("/mi-cuenta")
    async def mi_cuenta(usuario: dict = Depends(obtener_usuario_actual)):
        return usuario
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticación requerida",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    
    payload = TokenManager.verificar_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("tipo") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere un token de acceso",
            headers={"WWW-Authenticate": "Bearer"},
        )

    db = SessionLocal()
    try:
        token_persistido = db.query(TokenModel).filter(
            TokenModel.token_value == token,
            TokenModel.tipo_token == "access",
            TokenModel.activo.is_(True),
        ).first()
        if not token_persistido or (
            token_persistido.fecha_expiracion
            and token_persistido.fecha_expiracion < datetime.now()
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token revocado o expirado",
                headers={"WWW-Authenticate": "Bearer"},
            )
    finally:
        db.close()
    
    cuenta_id = payload.get("sub")
    if not cuenta_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sin información de usuario",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if str(token_persistido.cuenta_id) != str(cuenta_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token no corresponde a la cuenta",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Obtener información de la cuenta
    try:
        repository = CuentaRepositoryImpl()
        handler = ObtenerCuentaQueryHandler(repository)
        query = ObtenerCuentaQuery(cuenta_id=UUID(cuenta_id))
        cuenta_data = handler.handle(query)
        
        if not cuenta_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Cuenta no encontrada",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if (
            not cuenta_data.get("activa", True)
            or cuenta_data["estado"] in {"inactiva", "suspendida"}
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="La cuenta no está habilitada",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return {
            "cuenta_id": cuenta_data["cuenta_id"],
            "email": cuenta_data["email"],
            "rol": cuenta_data["rol"],
            "estado": cuenta_data["estado"]
        }
    
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Error al verificar usuario",
            headers={"WWW-Authenticate": "Bearer"},
        )
