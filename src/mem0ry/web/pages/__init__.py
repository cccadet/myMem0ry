"""Web UI page handlers split by responsibility."""

from __future__ import annotations

from .audit import audit_page
from .dashboard import dashboard
from .handoffs import (
    close_handoff_page,
    delete_handoff_page,
    handoff_detail,
    handoffs_page,
)
from .import_export import (
    export_memories_page,
    export_page,
    import_memories_page,
    import_page,
)
from .memories import (
    api_memories,
    batch_delete_memories,
    delete_memory_page,
    memory_detail,
    memory_edit_form,
    memory_edit_save,
    pin_memory_page,
    restore_memory_page,
    unpin_memory_page,
)
from .observations import delete_observation_page, observation_detail
from .projects import project_detail, project_observations, projects_page
from .search import search_page
from .shared import PAGE_SIZE, SORTS, SOURCES
from .trash import trash_page

__all__ = [
    "SOURCES",
    "SORTS",
    "PAGE_SIZE",
    "api_memories",
    "audit_page",
    "batch_delete_memories",
    "close_handoff_page",
    "dashboard",
    "delete_handoff_page",
    "delete_memory_page",
    "delete_observation_page",
    "export_memories_page",
    "export_page",
    "handoff_detail",
    "handoffs_page",
    "import_memories_page",
    "import_page",
    "memory_detail",
    "memory_edit_form",
    "memory_edit_save",
    "observation_detail",
    "pin_memory_page",
    "project_detail",
    "project_observations",
    "projects_page",
    "restore_memory_page",
    "search_page",
    "trash_page",
    "unpin_memory_page",
]
