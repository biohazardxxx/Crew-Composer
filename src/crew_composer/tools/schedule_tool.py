from __future__ import annotations

import json
import uuid
from typing import Any, Dict, Optional

from pydantic import Field
from crewai_tools import BaseTool  # type: ignore

from ..scheduler import (
    ScheduleEntry,
    delete_schedule,
    list_schedules,
    upsert_schedule,
)


class ScheduleManagerTool(BaseTool):
    """Manage scheduler entries from within a crew.

    Usage (pass JSON as input):
      {
        "action": "upsert" | "delete" | "list",
        "id": "optional-identifier",
        "name": "Report job",
        "crew": "my_crew",  # optional, defaults to first crew if omitted
        "trigger": "date" | "interval" | "cron",
        "run_at": "2025-09-19T10:00:00",
        "interval_seconds": 3600,
        "cron": {"minute": "0", "hour": "*"},
        "timezone": "UTC",
        "enabled": true,
        "inputs": {"topic": "My Topic"}
      }
    """

    name: str = "schedule_manager"
    description: str = (
        "Create, update, delete, or list scheduled runs for crews. "
        "Input must be a JSON string with an 'action' field."
    )

    # Optional defaults for convenience when tool is configured
    default_crew: Optional[str] = None
    default_trigger: Optional[str] = None
    default_timezone: Optional[str] = None

    # Expose return_direct to optionally keep LLM outputs concise
    return_direct: bool = Field(default=False)

    def _run(self, query: str) -> str:
        # query is expected to be a JSON string
        payload: Dict[str, Any]
        try:
            payload = json.loads(query or "{}")
        except Exception as e:  # noqa: BLE001
            return f"Invalid JSON input: {e}"

        action = str(payload.get("action", "")).strip().lower()
        if not action:
            return "Missing 'action'. Expected one of: upsert, delete, list"

        if action == "list":
            entries = list_schedules()
            return json.dumps([e.model_dump() for e in entries], indent=2)

        if action == "delete":
            sid = str(payload.get("id", "")).strip()
            if not sid:
                return "Missing 'id' for delete action"
            ok = delete_schedule(sid)
            return json.dumps({"deleted": ok, "id": sid})

        if action == "upsert":
            # Build ScheduleEntry with validations
            schedule_id = str(payload.get("id") or uuid.uuid4())
            name = str(payload.get("name", schedule_id))
            crew = str(payload.get("crew", self.default_crew or "") or None) or None
            trigger = str(payload.get("trigger", self.default_trigger or "date")).lower()
            if trigger not in ("date", "interval", "cron"):
                return "Invalid 'trigger'. Must be one of: date, interval, cron"

            entry = ScheduleEntry(
                id=schedule_id,
                name=name,
                crew=crew,
                trigger=trigger,  # type: ignore[arg-type]
                run_at=payload.get("run_at"),
                interval_seconds=payload.get("interval_seconds"),
                cron=payload.get("cron"),
                timezone=str(payload.get("timezone", self.default_timezone or "")) or None,
                enabled=bool(payload.get("enabled", True)),
                inputs=payload.get("inputs") or {},
            )
            saved = upsert_schedule(entry)
            return json.dumps(saved.model_dump(), indent=2)

        return "Unsupported action. Use: upsert, delete, list"
