"""Read-only web UI for myMem0ry — dark mode, mounted on MCP server."""

from __future__ import annotations

from starlette.routing import Route

from .pages import (
    dashboard,
    projects_page,
    project_detail,
    memory_detail,
    memory_edit_form,
    memory_edit_save,
    pin_memory_page,
    unpin_memory_page,
    observation_detail,
    search_page,
    audit_page,
    api_memories,
    delete_memory_page,
    delete_observation_page,
    trash_page,
    restore_memory_page,
    handoffs_page,
    handoff_detail,
    close_handoff_page,
    delete_handoff_page,
    batch_delete_memories,
    export_memories_page,
    import_page,
    import_memories_page,
)
from .templates import _db_path  # noqa: F401


def get_web_routes() -> list[Route]:
    return [
        Route("/", dashboard),
        Route("/projects", projects_page),
        Route("/project/{project_id:path}", project_detail),
        Route("/memory/{memory_id}", memory_detail),
        Route("/memory/{memory_id}/edit", memory_edit_form),
        Route("/memory/{memory_id}/edit", memory_edit_save, methods=["POST"]),
        Route("/memory/{memory_id}/pin", pin_memory_page, methods=["POST"]),
        Route("/memory/{memory_id}/unpin", unpin_memory_page, methods=["POST"]),
        Route("/memory/{memory_id}/restore", restore_memory_page, methods=["POST"]),
        Route("/memory/{memory_id}/delete", delete_memory_page, methods=["POST"]),
        Route("/observation/{observation_id}", observation_detail),
        Route("/observation/{observation_id}/delete", delete_observation_page, methods=["POST"]),
        Route("/trash", trash_page),
        Route("/handoffs", handoffs_page),
        Route("/handoff/{handoff_id}", handoff_detail),
        Route("/handoff/{handoff_id}/close", close_handoff_page, methods=["POST"]),
        Route("/handoff/{handoff_id}/delete", delete_handoff_page, methods=["POST"]),
        Route("/search", search_page),
        Route("/audit", audit_page),
        Route("/api/memories", api_memories),
        Route("/memories/batch-delete", batch_delete_memories, methods=["POST"]),
        Route("/memories/export", export_memories_page, methods=["POST"]),
        Route("/import", import_page),
        Route("/memories/import", import_memories_page, methods=["POST"]),
    ]
