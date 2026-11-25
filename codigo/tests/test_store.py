import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from temporal_reconstruction.models import EventInput, ReconstructionMode, TaskState
from temporal_reconstruction.exporter import build_engine_artifacts
from temporal_reconstruction.store import EventStore


def instant(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def event(identifier: str, task: str, kind: str, occurred: str, received: str, available: str) -> EventInput:
    return EventInput(identifier, task, kind, instant(occurred), instant(received), instant(available))


class EventStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.store = EventStore(Path(self.temporary_directory.name) / "replay.db")
        self.store.initialize()

    def tearDown(self) -> None:
        self.store.close()
        self.temporary_directory.cleanup()

    def test_availability_prevents_future_information_leakage(self) -> None:
        self.store.ingest([
            event("created", "42", "task_created", "2026-11-17T08:00:00Z", "2026-11-17T08:00:01Z", "2026-11-17T08:00:01Z"),
            event("completed-late", "42", "task_completed", "2026-11-18T09:00:00Z", "2026-11-20T09:00:00Z", "2026-11-20T09:01:00Z"),
        ])
        cutoff = instant("2026-11-19T12:00:00Z")

        naive = self.store.reconstruct(cutoff, ReconstructionMode.OCCURRENCE)
        faithful = self.store.reconstruct(cutoff, ReconstructionMode.AVAILABILITY)

        self.assertEqual(naive[0].state, TaskState.COMPLETED)
        self.assertEqual(faithful[0].state, TaskState.OPEN)
        self.assertEqual(faithful[0].source_event_id, "created")

    def test_reconstruction_handles_out_of_order_ingestion(self) -> None:
        self.store.ingest([event("completed", "7", "task_completed", "2026-11-18T11:00:00Z", "2026-11-18T11:02:00Z", "2026-11-18T11:03:00Z")])
        self.store.ingest([event("started", "7", "task_started", "2026-11-18T10:00:00Z", "2026-11-18T12:00:00Z", "2026-11-18T12:01:00Z")])

        state = self.store.reconstruct(instant("2026-11-18T12:30:00Z"), ReconstructionMode.AVAILABILITY)

        self.assertEqual(state[0].state, TaskState.COMPLETED)
        self.assertEqual(state[0].source_event_id, "completed")

    def test_duplicate_source_event_is_idempotent(self) -> None:
        created = event("event-1", "21", "task_created", "2026-11-18T10:00:00Z", "2026-11-18T10:01:00Z", "2026-11-18T10:01:00Z")

        self.assertEqual(self.store.ingest([created]), 1)
        self.assertEqual(self.store.ingest([created]), 0)
        states = self.store.reconstruct(instant("2026-11-19T00:00:00Z"), ReconstructionMode.AVAILABILITY)
        self.assertEqual(len(states), 1)

    def test_invalid_temporal_order_is_rejected(self) -> None:
        invalid = event("bad", "1", "task_created", "2026-11-18T10:00:00Z", "2026-11-18T09:00:00Z", "2026-11-18T11:00:00Z")
        with self.assertRaisesRegex(ValueError, "occurred_at"):
            self.store.ingest([invalid])

    def test_export_preserves_lineage_and_go_engine_contract(self) -> None:
        self.store.ingest([event("done", "github-42", "task_completed", "2026-11-18T10:00:00Z", "2026-11-18T10:01:00Z", "2026-11-18T10:02:00Z")])
        template = {
            "status_date": 2.0,
            "tasks": [{"id": "T1", "source_task_id": "github-42", "name": "Replay", "to": 1.0, "tm": 2.0, "tp": 3.0}],
            "dependencies": [], "risks": [],
        }
        cutoff = instant("2026-11-19T00:00:00Z")
        network, provenance = build_engine_artifacts(
            template, self.store.reconstruct(cutoff, ReconstructionMode.AVAILABILITY), cutoff, ReconstructionMode.AVAILABILITY
        )

        self.assertEqual(set(network), {"tasks", "dependencies", "risks", "status_date"})
        self.assertEqual(network["tasks"][0]["completed"], True)
        self.assertEqual(network["tasks"][0]["progress"], 1.0)
        self.assertEqual(provenance["tasks"][0]["source_event_id"], "done")


if __name__ == "__main__":
    unittest.main()
