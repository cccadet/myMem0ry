"""Authentication and security middleware for the myMem0ry MCP server."""

from __future__ import annotations

import secrets
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


def check_bearer(token: str | None, expected: str | None) -> bool:
    """Constant-time bearer token comparison. Skip if no token configured."""
    if not expected:
        return True
    if not token:
        return False
    if token.startswith("Bearer "):
        token = token[7:]
    return secrets.compare_digest(token, expected)


def check_host(host_header: str | None, allowed: set[str]) -> bool:
    """Check Host header against allowlist for DNS rebinding protection."""
    if not allowed:
        return True
    if not host_header:
        return False
    hostname = host_header.split(":")[0].lower()
    return hostname in allowed or host_header.lower() in allowed


class AuthMiddleware(BaseHTTPMiddleware):
    """Bearer token auth + Host allowlisting for HTTP endpoints."""

    def __init__(
        self,
        app: Any,
        auth_token: str | None = None,
        allowed_hosts: set[str] | None = None,
    ) -> None:
        super().__init__(app)
        self._token = auth_token
        self._hosts = allowed_hosts or set()

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        host = request.headers.get("host", "")
        if self._hosts and not check_host(host, self._hosts):
            return JSONResponse({"error": "Host not allowed"}, status_code=403)

        auth_header = request.headers.get("authorization", "")
        if not check_bearer(auth_header, self._token):
            return JSONResponse({"error": "Unauthorized"}, status_code=401)

        response = await call_next(request)
        return response


class CORSMiddleware(BaseHTTPMiddleware):
    """Simple CORS middleware for future web UI support."""

    def __init__(self, app: Any, origins: str = "") -> None:
        super().__init__(app)
        self._origins = origins

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        response = await call_next(request)

        if self._origins:
            response.headers["Access-Control-Allow-Origin"] = self._origins
            response.headers["Access-Control-Allow-Methods"] = (
                "GET, POST, PUT, DELETE, OPTIONS"
            )
            response.headers["Access-Control-Allow-Headers"] = (
                "Content-Type, Authorization"
            )
            response.headers["Access-Control-Max-Age"] = "86400"

        if request.method == "OPTIONS":
            response.status_code = 204

        return response


def parse_allowed_hosts(raw: str) -> set[str]:
    """Parse comma-separated host allowlist string."""
    if not raw:
        return set()
    return {h.strip().lower() for h in raw.split(",") if h.strip()}
