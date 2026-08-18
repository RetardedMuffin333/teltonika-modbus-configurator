"""Command-line entry point."""

from __future__ import annotations

import argparse
from getpass import getpass
from pathlib import Path

from .deploy import (
    SshSession,
    apply_generated,
    new_snapshot_name,
    read_remote_config,
    render_diff,
    rollback_snapshot,
    save_local_backup,
)
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


def _add_ssh_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=22)
    parser.add_argument("--user", default="root")
    parser.add_argument("--key", type=Path)
    parser.add_argument(
        "--trust-new-host",
        action="store_true",
        help="Accept and remember an SSH host key not already in known_hosts",
    )


def _open_ssh(args) -> SshSession:
    password = None
    if args.key is None:
        password = getpass(f"SSH password for {args.user}@{args.host}: ")
    return SshSession(
        args.host,
        username=args.user,
        port=args.port,
        password=password,
        key_filename=str(args.key) if args.key else None,
        trust_new_host=args.trust_new_host,
    )


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

    remote_preview_cmd = sub.add_parser(
        "remote-preview", help="Compare generated UCI with the live TRB over SSH"
    )
    remote_preview_cmd.add_argument("project", type=Path)
    _add_ssh_args(remote_preview_cmd)

    apply_cmd = sub.add_parser(
        "apply", help="Backup, validate and apply generated UCI to a live TRB"
    )
    apply_cmd.add_argument("project", type=Path)
    apply_cmd.add_argument("--backup-dir", type=Path, default=Path("backups"))
    apply_cmd.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    _add_ssh_args(apply_cmd)

    rollback_cmd = sub.add_parser(
        "rollback", help="Restore a remote snapshot previously created by tmc apply"
    )
    rollback_cmd.add_argument("snapshot", help="Snapshot name, e.g. 20260818T090000Z")
    _add_ssh_args(rollback_cmd)

    args = parser.parse_args()

    if args.command == "rollback":
        with _open_ssh(args) as session:
            rollback_snapshot(session, args.snapshot)
        print(f"Rolled back remote snapshot {args.snapshot}")
        return 0

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

    if args.command in {"remote-preview", "apply"}:
        with _open_ssh(args) as session:
            current = read_remote_config(session)
            diff = render_diff(current, generated)
            if diff:
                print(diff, end="" if diff.endswith("\n") else "\n")
            else:
                print("Live configuration already matches generated configuration.")

            if args.command == "remote-preview":
                return 0

            if not diff:
                print("Nothing to apply.")
                return 0

            if not args.yes:
                answer = input("Apply these changes to the TRB? Type 'apply' to continue: ")
                if answer.strip().lower() != "apply":
                    print("Cancelled.")
                    return 1

            snapshot = new_snapshot_name()
            local_backup = save_local_backup(current, args.backup_dir, snapshot)
            print(f"Saved local backup: {local_backup}")
            print(f"Creating remote snapshot: {snapshot}")
            apply_generated(session, generated, snapshot=snapshot)
            print("Apply complete.")
            print(f"Rollback with: tmc rollback {snapshot} --host {args.host}")
            return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
