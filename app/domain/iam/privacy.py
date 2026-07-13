"""Reglas de privacidad para los datos de contacto de una cuenta."""

from typing import Any, Mapping, Optional


MOSTRAR_EMAIL_PERFIL_KEY = "mostrar_email"


def mostrar_email_publicamente(
    perfil: Optional[Mapping[str, Any]],
) -> bool:
    """Indica si el correo de un postulante puede mostrarse a una empresa.

    Los perfiles creados antes de esta preferencia no contienen la clave y
    conservan el comportamiento anterior (correo visible). Si existe una
    clave con un valor mal formado, se adopta el criterio seguro y se oculta.
    """

    if not isinstance(perfil, Mapping) or MOSTRAR_EMAIL_PERFIL_KEY not in perfil:
        return True
    return perfil[MOSTRAR_EMAIL_PERFIL_KEY] is True


def email_visible_para_usuario(
    cuenta_data: Mapping[str, Any],
    usuario: Mapping[str, Any],
) -> bool:
    """Aplica la preferencia solo al acceso empresa -> postulante ajeno."""

    if str(cuenta_data.get("cuenta_id")) == str(usuario.get("cuenta_id")):
        return True
    if usuario.get("rol") != "empresa" or cuenta_data.get("rol") != "postulante":
        return True
    return mostrar_email_publicamente(cuenta_data.get("perfil"))
