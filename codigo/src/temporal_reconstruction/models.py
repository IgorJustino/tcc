from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class TaskState(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ReconstructionMode(StrEnum):
    OCCURRENCE = "occurrence"
    AVAILABILITY = "availability"


EVENT_TRANSITIONS: dict[str, TaskState] = {
    "task_created": TaskState.OPEN,
    "task_started": TaskState.IN_PROGRESS,
    "task_completed": TaskState.COMPLETED,
    "task_reopened": TaskState.OPEN,
    "task_cancelled": TaskState.CANCELLED,
}


@dataclass(frozen=True)
class EventInput:
    source_event_id: str
    task_id: str
    event_type: str
    occurred_at: datetime
    received_at: datetime
    available_at: datetime


@dataclass(frozen=True)
class ReconstructedState:
    task_id: str
    state: TaskState
    source_event_id: str
    occurred_at: datetime
    available_at: datetime
