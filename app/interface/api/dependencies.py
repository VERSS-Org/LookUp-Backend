from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional

from app.infrastructure.iam.security import TokenManager
from app.infrastructure.iam.repositories import CuentaRepositoryImpl
from app.application.iam.query_handlers import ObtenerCuentaQueryHandler, ObtenerCuentaQuery
from uuid import UUID

security = HTTPBearer()


async def obtener_usuario_actual(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Dependencia para obtener el usuario actual a partir del token JWT.
    
    Uso:
    @router.get("/mi-cuenta")
    async def mi_cuenta(usuario: dict = Depends(obtener_usuario_actual)):
        return usuario
    """
    token = credentials.credentials
    
    payload = TokenManager.verificar_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    cuenta_id = payload.get("sub")
    if not cuenta_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sin información de usuario",
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


async def obtener_usuario_con_rol(roles_permitidos: list = None):
    """
    Dependencia para obtener el usuario actual y validar que tenga un rol específico.
    
    Uso:
    from functools import partial
    admin_only = partial(obtener_usuario_con_rol, roles_permitidos=["admin"])
    
    @router.get("/panel-admin")
    async def panel_admin(usuario: dict = Depends(admin_only)):
        return {"mensaje": "Bienvenido admin"}
    """
    async def verificar_rol(usuario: dict = Depends(obtener_usuario_actual)) -> dict:
        if roles_permitidos and usuario["rol"] not in roles_permitidos:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Rol insuficiente. Roles permitidos: {roles_permitidos}"
            )
        return usuario
    
    return verificar_rol
