"""Read-only web UI for myMem0ry — dark mode, mounted on MCP server."""

from __future__ import annotations

from starlette.routing import Route

from .pages import (
    dashboard,
    projects_page,
    project_detail,
    memory_detail,
    observation_detail,
    search_page,
    audit_page,
    api_memories,
    delete_memory_page,
    delete_observation_page,
)
from .templates import _db_path  # noqa: F401


def get_web_routes() -> list[Route]:
    return [
        Route("/", dashboard),
        Route("/projects", projects_page),
        Route("/project/{project_id:path}", project_detail),
        Route("/memory/{memory_id}", memory_detail),
        Route("/memory/{memory_id}/delete", delete_memory_page, methods=["POST"]),
        Route("/observation/{observation_id}", observation_detail),
        Route("/observation/{observation_id}/delete", delete_observation_page, methods=["POST"]),
        Route("/search", search_page),
        Route("/audit", audit_page),
        Route("/api/memories", api_memories),
    ]
