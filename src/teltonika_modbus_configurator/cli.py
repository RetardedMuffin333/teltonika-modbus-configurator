"""Command-line entry point."""

from __future__ import annotations

import argparse
from pathlib import Path

from .loader import load_project
from .uci_generator import generate_uci
from .validator import validate_project


def _print_validation(project) -> bool:
    messages = validate_project(project)
    for item in messages:
        print(f"{item.level.upper()}: {item.message}")
    if not messages:
        print("Validation: PASS")
    return not any(item.level == "error" for item in messages)


def main() -> int:
    parser = argparse.ArgumentParser(prog="tmc")
    sub = parser.add_subparsers(dest="command", required=True)

    validate_cmd = sub.add_parser("validate", help="Validate a YAML project")
    validate_cmd.add_argument("project", type=Path)

    preview_cmd = sub.add_parser("preview", help="Print generated RutOS UCI")
    preview_cmd.add_argument("project", type=Path)

    export_cmd = sub.add_parser("export", help="Generate modbus_client and modbus_server files")
    export_cmd.add_argument("project", type=Path)
    export_cmd.add_argument("--output", "-o", type=Path, default=Path("output"))

    args = parser.parse_args()
    project = load_project(args.project)

    if args.command == "validate":
        return 0 if _print_validation(project) else 1

    if not _print_validation(project):
        return 1

    generated = generate_uci(project)

    if args.command == "preview":
        print("# ===== modbus_client =====")
        print(generated.modbus_client, end="")
        print("\n# ===== modbus_server =====")
        print(generated.modbus_server, end="")
        return 0

    if args.command == "export":
        args.output.mkdir(parents=True, exist_ok=True)
        client_path = args.output / "modbus_client"
        server_path = args.output / "modbus_server"
        client_path.write_text(generated.modbus_client, encoding="utf-8")
        server_path.write_text(generated.modbus_server, encoding="utf-8")
        print(f"Wrote {client_path}")
        print(f"Wrote {server_path}")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
