from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from .exporter import build_engine_artifacts, load_network_template, write_json
from .models import EventInput, ReconstructionMode
from .store import EventStore


def parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("informe o fuso horário, por exemplo Z")
    return parsed


def read_events(path: Path) -> list[EventInput]:
    items = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(items, list):
        raise ValueError("a entrada JSON deve ser uma lista de eventos")
    return [
        EventInput(
            source_event_id=item["source_event_id"], task_id=item["task_id"],
            event_type=item["event_type"], occurred_at=parse_datetime(item["occurred_at"]),
            received_at=parse_datetime(item["received_at"]), available_at=parse_datetime(item["available_at"]),
        )
        for item in items
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconstrução temporal de tarefas")
    parser.add_argument("--database", required=True, type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init")
    ingest = commands.add_parser("ingest")
    ingest.add_argument("--input", required=True, type=Path)
    reconstruct = commands.add_parser("reconstruct")
    reconstruct.add_argument("--cutoff", required=True, type=parse_datetime)
    reconstruct.add_argument("--mode", choices=list(ReconstructionMode), required=True, type=ReconstructionMode)
    export = commands.add_parser("export-network")
    export.add_argument("--cutoff", required=True, type=parse_datetime)
    export.add_argument("--mode", choices=list(ReconstructionMode), required=True, type=ReconstructionMode)
    export.add_argument("--template", required=True, type=Path)
    export.add_argument("--output", required=True, type=Path)
    export.add_argument("--provenance-output", required=True, type=Path)
    arguments = parser.parse_args()

    store = EventStore(arguments.database)
    try:
        store.initialize()
        if arguments.command == "ingest":
            print(json.dumps({"inserted": store.ingest(read_events(arguments.input))}))
        elif arguments.command == "reconstruct":
            states = store.reconstruct(arguments.cutoff, arguments.mode)
            print(json.dumps([
                {"task_id": state.task_id, "state": state.state,
                 "source_event_id": state.source_event_id,
                 "occurred_at": state.occurred_at.isoformat(),
                 "available_at": state.available_at.isoformat()}
                for state in states
            ], indent=2))
        elif arguments.command == "export-network":
            states = store.reconstruct(arguments.cutoff, arguments.mode)
            network, provenance = build_engine_artifacts(
                load_network_template(arguments.template), states, arguments.cutoff, arguments.mode
            )
            write_json(arguments.output, network)
            write_json(arguments.provenance_output, provenance)
            print(json.dumps({"network": str(arguments.output), "provenance": str(arguments.provenance_output)}))
    finally:
        store.close()


if __name__ == "__main__":
    main()
