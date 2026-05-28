"""Read-only web UI for myMem0ry — dark mode, mounted on MCP server."""

from __future__ import annotations

from starlette.routing import Route

from .pages import (
    dashboard,
    projects_page,
    project_detail,
    memory_detail,
    search_page,
    audit_page,
    api_memories,
)
from .templates import _db_path  # noqa: F401


def get_web_routes() -> list[Route]:
    return [
        Route("/", dashboard),
        Route("/projects", projects_page),
        Route("/project/{project_id:path}", project_detail),
        Route("/memory/{memory_id}", memory_detail),
        Route("/search", search_page),
        Route("/audit", audit_page),
        Route("/api/memories", api_memories),
    ]
