from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import ReconstructedState, ReconstructionMode, TaskState


NETWORK_FIELDS = ("tasks", "dependencies", "risks", "status_date")
TASK_FIELDS = ("id", "name", "to", "tm", "tp", "progress", "actual_duration", "completed")


def load_network_template(path: Path) -> dict[str, Any]:
    template = json.loads(path.read_text(encoding="utf-8"))
    missing = [field for field in NETWORK_FIELDS if field not in template]
    if missing:
        raise ValueError(f"modelo de rede sem campos obrigatórios: {', '.join(missing)}")
    if not isinstance(template["tasks"], list):
        raise ValueError("tasks deve ser uma lista")
    return template


def build_engine_artifacts(
    template: dict[str, Any], states: Iterable[ReconstructedState], cutoff: datetime, mode: ReconstructionMode
) -> tuple[dict[str, Any], dict[str, Any]]:
    states_by_task = {state.task_id: state for state in states}
    network_tasks: list[dict[str, Any]] = []
    lineage: list[dict[str, Any]] = []

    for source_task in template["tasks"]:
        for required in ("id", "name", "to", "tm", "tp"):
            if required not in source_task:
                raise ValueError(f"tarefa sem campo obrigatório {required!r}")
        source_task_id = source_task.get("source_task_id", source_task["id"])
        state = states_by_task.get(source_task_id)
        completed = state is not None and state.state == TaskState.COMPLETED
        task = {
            "id": source_task["id"], "name": source_task["name"],
            "to": source_task["to"], "tm": source_task["tm"], "tp": source_task["tp"],
            "progress": 1.0 if completed else 0.0,
            "actual_duration": source_task.get("actual_duration", 0.0),
            "completed": completed,
        }
        network_tasks.append(task)
        lineage.append({
            "engine_task_id": source_task["id"], "source_task_id": source_task_id,
            "state": state.state if state else None,
            "source_event_id": state.source_event_id if state else None,
            "event_occurred_at": state.occurred_at.isoformat() if state else None,
            "event_available_at": state.available_at.isoformat() if state else None,
        })

    network = {
        "tasks": network_tasks,
        "dependencies": template["dependencies"],
        "risks": template["risks"],
        "status_date": template["status_date"],
    }
    provenance = {
        "contract_version": "1.0",
        "reconstruction_mode": mode,
        "cutoff": cutoff.isoformat(),
        "tasks": lineage,
    }
    return network, provenance


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
