import asyncio

from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

import pytest

from app.config import Settings


async def _empty_asgi_app(scope, receive, send):
    del scope, receive, send


def _cors_middleware(config: Settings) -> CORSMiddleware:
    return CORSMiddleware(
        app=_empty_asgi_app,
        allow_origins=config.CORS_ORIGINS,
        allow_origin_regex=config.CORS_ORIGIN_REGEX,
        allow_credentials="*" not in config.CORS_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )


async def _preflight(middleware: CORSMiddleware, origin: str):
    messages = []
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "scheme": "http",
        "method": "OPTIONS",
        "path": "/api/iam/registrar",
        "raw_path": b"/api/iam/registrar",
        "query_string": b"",
        "root_path": "",
        "headers": [
            (b"origin", origin.encode()),
            (b"access-control-request-method", b"POST"),
            (b"access-control-request-headers", b"content-type"),
        ],
        "client": ("127.0.0.1", 54321),
        "server": ("127.0.0.1", 8000),
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    await middleware(scope, receive, send)
    response_start = next(
        message for message in messages if message["type"] == "http.response.start"
    )
    return response_start["status"], dict(response_start["headers"])


@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost:8085",
        "http://localhost:8095",
        "http://127.0.0.1:8085",
        "https://127.0.0.1:49152",
        "http://localhost",
    ],
)
def test_cors_de_desarrollo_acepta_origenes_locales_en_cualquier_puerto(origin):
    config = Settings(_env_file=None, ENVIRONMENT="development")

    assert _cors_middleware(config).is_allowed_origin(origin)


@pytest.mark.parametrize("origin", ["http://localhost:8085", "http://localhost:8095"])
def test_preflight_de_registro_devuelve_los_headers_cors(origin):
    config = Settings(_env_file=None, ENVIRONMENT="development")

    status, headers = asyncio.run(_preflight(_cors_middleware(config), origin))

    assert status == 200
    assert headers[b"access-control-allow-origin"] == origin.encode()
    assert b"POST" in headers[b"access-control-allow-methods"]


@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost.evil.example:8085",
        "http://127.0.0.2:8085",
        "http://example.com:8085",
    ],
)
def test_cors_de_desarrollo_no_abre_hosts_externos(origin):
    config = Settings(_env_file=None, ENVIRONMENT="development")

    assert not _cors_middleware(config).is_allowed_origin(origin)


def test_cors_de_produccion_solo_acepta_origenes_explicitos():
    config = Settings(
        _env_file=None,
        ENVIRONMENT="production",
        SECRET_KEY="a-secure-production-secret-with-32-characters",
        CORS_ORIGINS=["https://empresas.lookup.example"],
    )
    middleware = _cors_middleware(config)

    assert config.CORS_ORIGIN_REGEX is None
    assert middleware.is_allowed_origin("https://empresas.lookup.example")
    assert not middleware.is_allowed_origin("http://localhost:8095")


def test_cors_de_produccion_rechaza_comodin():
    with pytest.raises(ValidationError, match="no puede contener"):
        Settings(
            _env_file=None,
            ENVIRONMENT="production",
            SECRET_KEY="a-secure-production-secret-with-32-characters",
            CORS_ORIGINS=["*"],
        )
