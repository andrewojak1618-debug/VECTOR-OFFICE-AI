"""Inspect and maintain the bounded local tool audit without external access."""

import argparse
import json
import sqlite3
from collections.abc import Sequence

from config.settings import settings
from tools.audit_store import SQLiteToolAuditStore, ToolAuditRecord


CLEAR_CONFIRMATION = "DELETE"


def main(argv: Sequence[str] | None = None) -> int:
    """Run one local audit maintenance command and return a status code."""
    arguments = _argument_parser().parse_args(argv)
    try:
        store = SQLiteToolAuditStore(
            settings.MEMORY_DB_PATH,
            settings.TOOL_AUDIT_RETENTION_DAYS,
            settings.TOOL_AUDIT_MAX_ENTRIES,
        )
        return _run_command(store, arguments)
    except (OSError, sqlite3.Error, TypeError, ValueError):
        print("Local tool audit could not be read. [ERROR]")
        return 1


def _run_command(store: SQLiteToolAuditStore, arguments) -> int:
    if arguments.command == "list":
        _print_records(store.list_events(arguments.limit))
        return 0
    if arguments.command == "prune":
        print(f"Removed audit records: {store.prune()}")
        return 0
    if arguments.confirm != CLEAR_CONFIRMATION:
        print(f"Clearing requires --confirm {CLEAR_CONFIRMATION}. [BLOCKED]")
        return 2
    print(f"Removed audit records: {store.clear()}")
    return 0


def _print_records(records: Sequence[ToolAuditRecord]) -> None:
    if not records:
        print("No local tool audit records.")
        return
    for record in records:
        permission = record.permission.value if record.permission else "unknown"
        arguments = json.dumps(
            dict(record.arguments),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        error = record.error_code or "none"
        print(
            f"{record.id} | {record.occurred_at} | {record.tool_name} | "
            f"{permission} | {record.status.value} | {error} | {arguments}"
        )


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Maintain local tool audit data.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    list_parser = subparsers.add_parser("list", help="List newest records.")
    list_parser.add_argument("--limit", type=int, default=20)
    subparsers.add_parser("prune", help="Apply configured retention now.")
    clear_parser = subparsers.add_parser("clear", help="Delete all audit records.")
    clear_parser.add_argument("--confirm", default="")
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
