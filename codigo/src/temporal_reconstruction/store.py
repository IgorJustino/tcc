from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .models import EVENT_TRANSITIONS, EventInput, ReconstructedState, ReconstructionMode, TaskState


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamps precisam incluir fuso horário")
    return parsed.astimezone(timezone.utc)


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("timestamps precisam incluir fuso horário")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class EventStore:
    """Persistência idempotente e consultas de reconstrução temporal."""

    def __init__(self, database: str | Path) -> None:
        self.connection = sqlite3.connect(database)
        self.connection.row_factory = sqlite3.Row

    def close(self) -> None:
        self.connection.close()

    def initialize(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                source_event_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                received_at TEXT NOT NULL,
                available_at TEXT NOT NULL,
                CHECK(available_at >= received_at),
                CHECK(received_at >= occurred_at)
            )
            """
        )
        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_task_occurrence "
            "ON events(task_id, occurred_at, source_event_id)"
        )
        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_task_availability "
            "ON events(task_id, available_at, occurred_at, source_event_id)"
        )
        self.connection.commit()

    def ingest(self, events: Iterable[EventInput]) -> int:
        rows = []
        for event in events:
            if event.event_type not in EVENT_TRANSITIONS:
                raise ValueError(f"tipo de evento não suportado: {event.event_type}")
            if not event.source_event_id or not event.task_id:
                raise ValueError("source_event_id e task_id são obrigatórios")
            if not event.occurred_at <= event.received_at <= event.available_at:
                raise ValueError("esperado: occurred_at <= received_at <= available_at")
            rows.append((
                event.source_event_id, event.task_id, event.event_type,
                _timestamp(event.occurred_at), _timestamp(event.received_at), _timestamp(event.available_at),
            ))
        with self.connection:
            before = self.connection.total_changes
            self.connection.executemany(
                "INSERT OR IGNORE INTO events VALUES (?, ?, ?, ?, ?, ?)", rows
            )
            return self.connection.total_changes - before

    def reconstruct(self, cutoff: datetime, mode: ReconstructionMode) -> list[ReconstructedState]:
        cutoff_text = _timestamp(cutoff)
        time_column = "occurred_at" if mode == ReconstructionMode.OCCURRENCE else "available_at"
        rows = self.connection.execute(
            f"""
            WITH eligible AS (
                SELECT *, ROW_NUMBER() OVER (
                    PARTITION BY task_id
                    ORDER BY occurred_at DESC, available_at DESC, source_event_id DESC
                ) AS position
                FROM events
                WHERE {time_column} <= ?
            )
            SELECT * FROM eligible WHERE position = 1 ORDER BY task_id
            """,
            (cutoff_text,),
        ).fetchall()
        return [
            ReconstructedState(
                task_id=row["task_id"],
                state=EVENT_TRANSITIONS[row["event_type"]],
                source_event_id=row["source_event_id"],
                occurred_at=_parse_timestamp(row["occurred_at"]),
                available_at=_parse_timestamp(row["available_at"]),
            )
            for row in rows
        ]
