from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import TextIO

from companion.core import (
    _exchange_dir,
    _read_json_object,
    list_ready_calls,
    load_active_calls,
    prepare_call,
    stop_call,
)
from companion.downloads import default_downloads_dir, finalize_exchange, finish_call
from companion.repair import collect_defects, open_repair_round


def run(
    argv: list[str],
    *,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    parser = _parser()
    command = "unknown"
    try:
        options = parser.parse_args(argv)
        command = options.command
        root = Path(options.root).resolve()
        if command == "prepare":
            spec = _read_json_object(Path(options.spec), "preparation spec")
            created_at = spec.pop("created_at", None)
            now = datetime.fromisoformat(created_at) if created_at else datetime.now().astimezone()
            result = prepare_call(root, spec, now)
        elif command == "list":
            result = list_ready_calls(root)
        elif command == "show":
            exchange = _exchange_dir(root, options.exchange)
            result = _read_json_object(
                exchange / "EXCHANGE_MANIFEST.json", "EXCHANGE_MANIFEST"
            )
        elif command == "active":
            records = load_active_calls(root)
            if not records:
                result = None
            else:
                result = records[0] if len(records) == 1 else records
        elif command == "done":
            result = finish_call(
                root, options.exchange, _downloads_dir(options.downloads_dir)
            )
        elif command == "stop":
            result = stop_call(root, options.exchange)
        elif command == "validate":
            result = finalize_exchange(
                root, options.exchange, _downloads_dir(options.downloads_dir)
            )
        elif command == "defects":
            result = collect_defects(_exchange_dir(root, options.exchange))
        elif command == "repair":
            result = open_repair_round(
                root,
                options.exchange,
                options.tab,
                [],
            )
        else:
            raise ValueError(f"unsupported command: {command}")
    except (Exception, SystemExit) as error:
        message = str(error) or "invalid command arguments"
        json.dump(
            {"ok": False, "command": command, "error": message},
            stderr,
            ensure_ascii=False,
        )
        stderr.write("\n")
        return 2
    json.dump(
        {"ok": True, "command": command, "result": result},
        stdout,
        ensure_ascii=False,
    )
    stdout.write("\n")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(exit_on_error=False)
    parser.add_argument("--root", required=True)
    subcommands = parser.add_subparsers(dest="command", required=True)
    prepare = subcommands.add_parser("prepare", exit_on_error=False)
    prepare.add_argument("--spec", required=True)
    subcommands.add_parser("list", exit_on_error=False)
    show = subcommands.add_parser("show", exit_on_error=False)
    show.add_argument("--exchange", required=True)
    subcommands.add_parser("active", exit_on_error=False)
    done = subcommands.add_parser("done", exit_on_error=False)
    done.add_argument("--exchange", default=None)
    done.add_argument("--downloads-dir", default=None)
    stop = subcommands.add_parser("stop", exit_on_error=False)
    stop.add_argument("--exchange", default=None)
    validate = subcommands.add_parser("validate", exit_on_error=False)
    validate.add_argument("--exchange", required=True)
    validate.add_argument("--downloads-dir", default=None)
    defects = subcommands.add_parser("defects", exit_on_error=False)
    defects.add_argument("--exchange", required=True)
    repair = subcommands.add_parser("repair", exit_on_error=False)
    repair.add_argument("--exchange", required=True)
    repair.add_argument("--tab", type=int, default=None)
    return parser


def _downloads_dir(explicit: str | None) -> Path:
    """Where Chrome writes downloads before they are ingested.

    The explicit flag wins; otherwise this is the same resolution the side panel
    uses, so both entry points ingest from the same place.
    """
    return Path(explicit) if explicit else default_downloads_dir()


def main(argv: list[str] | None = None) -> int:
    return run(list(sys.argv[1:] if argv is None else argv))


if __name__ == "__main__":
    raise SystemExit(main())
