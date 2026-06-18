"""Additional tests for auth middleware helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from mem0ry.auth import (
    AuthMiddleware,
    CORSMiddleware,
    check_bearer,
    check_host,
    parse_allowed_hosts,
)


def test_check_bearer_no_token_configured() -> None:
    assert check_bearer("anything", None) is True
    assert check_bearer("", "") is True


def test_check_bearer_missing_token() -> None:
    assert check_bearer(None, "secret") is False
    assert check_bearer("", "secret") is False


def test_check_bearer_valid_token() -> None:
    assert check_bearer("secret", "secret") is True
    assert check_bearer("Bearer secret", "secret") is True


def test_check_bearer_invalid_token() -> None:
    assert check_bearer("wrong", "secret") is False
    assert check_bearer("Bearer wrong", "secret") is False


def test_check_host_no_allowlist() -> None:
    assert check_host("evil.com", set()) is True


def test_check_host_missing_header() -> None:
    assert check_host(None, {"localhost"}) is False


def test_check_host_allowed() -> None:
    assert check_host("localhost:49374", {"localhost"}) is True
    assert check_host("localhost", {"localhost"}) is True


def test_check_host_not_allowed() -> None:
    assert check_host("evil.com", {"localhost"}) is False


def test_parse_allowed_hosts() -> None:
    assert parse_allowed_hosts("") == set()
    assert parse_allowed_hosts("localhost, 127.0.0.1") == {"localhost", "127.0.0.1"}


@pytest.mark.anyio
async def test_auth_middleware_blocks_unknown_host() -> None:
    app = AsyncMock(return_value=Response("OK"))
    middleware = AuthMiddleware(app, auth_token=None, allowed_hosts={"localhost"})

    request = MagicMock(spec=Request)
    request.headers = {"host": "evil.com"}

    response = await middleware.dispatch(request, app)
    assert isinstance(response, JSONResponse)
    assert response.status_code == 403


@pytest.mark.anyio
async def test_auth_middleware_blocks_missing_token() -> None:
    app = AsyncMock(return_value=Response("OK"))
    middleware = AuthMiddleware(app, auth_token="secret", allowed_hosts=set())

    request = MagicMock(spec=Request)
    request.headers = {}

    response = await middleware.dispatch(request, app)
    assert isinstance(response, JSONResponse)
    assert response.status_code == 401


@pytest.mark.anyio
async def test_auth_middleware_allows_valid_request() -> None:
    app = AsyncMock(return_value=Response("OK"))
    middleware = AuthMiddleware(app, auth_token="secret", allowed_hosts={"localhost"})

    request = MagicMock(spec=Request)
    request.headers = {"host": "localhost", "authorization": "Bearer secret"}

    response = await middleware.dispatch(request, app)
    assert response.body == b"OK"


@pytest.mark.anyio
async def test_cors_middleware_adds_headers() -> None:
    app = AsyncMock(return_value=Response("OK"))
    middleware = CORSMiddleware(app, origins="http://localhost:3000")

    request = MagicMock(spec=Request)
    request.method = "GET"

    response = await middleware.dispatch(request, app)
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:3000"


@pytest.mark.anyio
async def test_cors_middleware_options_returns_204() -> None:
    app = AsyncMock(return_value=Response("OK"))
    middleware = CORSMiddleware(app, origins="http://localhost:3000")

    request = MagicMock(spec=Request)
    request.method = "OPTIONS"

    response = await middleware.dispatch(request, app)
    assert response.status_code == 204
