"""Safe SSH deployment helpers for RutOS devices."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import unified_diff
from pathlib import Path
from time import monotonic, sleep
from typing import Callable

import paramiko

from .uci_generator import GeneratedUci


DEFAULT_COMMAND_TIMEOUT = 45.0
ProgressCallback = Callable[[str], None]


@dataclass(slots=True)
class RemoteConfig:
    modbus_client: str
    modbus_server: str


class SshSession:
    def __init__(
        self,
        host: str,
        *,
        username: str = "root",
        port: int = 22,
        password: str | None = None,
        key_filename: str | None = None,
        trust_new_host: bool = False,
        command_timeout: float = DEFAULT_COMMAND_TIMEOUT,
    ) -> None:
        self.command_timeout = command_timeout
        self.client = paramiko.SSHClient()
        self.client.load_system_host_keys()
        if trust_new_host:
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        else:
            self.client.set_missing_host_key_policy(paramiko.RejectPolicy())
        self.client.connect(
            hostname=host,
            port=port,
            username=username,
            password=password,
            key_filename=key_filename,
            look_for_keys=key_filename is None and password is None,
            allow_agent=True,
            timeout=10,
        )

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "SshSession":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def run(
        self,
        command: str,
        *,
        stdin_text: str | None = None,
        timeout: float | None = None,
    ) -> str:
        stdin, stdout, stderr = self.client.exec_command(command)
        if stdin_text is not None:
            stdin.write(stdin_text)
            stdin.channel.shutdown_write()

        channel = stdout.channel
        effective_timeout = self.command_timeout if timeout is None else timeout
        deadline = monotonic() + effective_timeout
        while not channel.exit_status_ready():
            if monotonic() >= deadline:
                channel.close()
                raise TimeoutError(
                    f"Remote command timed out after {effective_timeout:.0f}s: {command}"
                )
            sleep(0.05)

        status = channel.recv_exit_status()
        output = stdout.read().decode("utf-8", errors="replace")
        error = stderr.read().decode("utf-8", errors="replace")
        if status != 0:
            raise RuntimeError(
                f"Remote command failed ({status}): {command}\n{error.strip()}"
            )
        return output


def _progress(callback: ProgressCallback | None, message: str) -> None:
    if callback is not None:
        callback(message)


def read_remote_config(session: SshSession) -> RemoteConfig:
    return RemoteConfig(
        modbus_client=session.run("uci export modbus_client"),
        modbus_server=session.run("uci export modbus_server"),
    )


def render_diff(current: RemoteConfig, proposed: GeneratedUci) -> str:
    chunks: list[str] = []
    for name, before, after in (
        ("modbus_client", current.modbus_client, proposed.modbus_client),
        ("modbus_server", current.modbus_server, proposed.modbus_server),
    ):
        chunks.extend(
            unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile=f"live/{name}",
                tofile=f"generated/{name}",
            )
        )
    return "".join(chunks)


def save_local_backup(config: RemoteConfig, directory: Path, snapshot: str) -> Path:
    target = directory / snapshot
    target.mkdir(parents=True, exist_ok=False)
    (target / "modbus_client").write_text(config.modbus_client, encoding="utf-8")
    (target / "modbus_server").write_text(config.modbus_server, encoding="utf-8")
    return target


def new_snapshot_name() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _verify_committed_config(session: SshSession) -> None:
    """Verify that both committed RutOS UCI packages remain readable."""
    session.run("uci export modbus_client >/dev/null")
    session.run("uci export modbus_server >/dev/null")


def apply_generated(
    session: SshSession,
    proposed: GeneratedUci,
    *,
    snapshot: str,
    progress: ProgressCallback | None = None,
) -> None:
    remote_dir = f"/root/tmc-backups/{snapshot}"
    _progress(progress, "Creating remote backup...")
    session.run(
        f"mkdir -p {remote_dir} && "
        f"cp /etc/config/modbus_client {remote_dir}/modbus_client && "
        f"cp /etc/config/modbus_server {remote_dir}/modbus_server"
    )

    committed = False
    try:
        _progress(progress, "Uploading Modbus Client configuration...")
        session.run("uci import modbus_client", stdin_text=proposed.modbus_client)
        _progress(progress, "Uploading Modbus Server configuration...")
        session.run("uci import modbus_server", stdin_text=proposed.modbus_server)

        _progress(progress, "Validating generated UCI...")
        session.run("uci export modbus_client >/dev/null")
        session.run("uci export modbus_server >/dev/null")

        _progress(progress, "Committing Modbus configuration...")
        session.run("uci commit modbus_client")
        session.run("uci commit modbus_server")
        committed = True

        _progress(progress, "Restarting Modbus services...")
        try:
            session.run(
                "([ -x /etc/init.d/modbus_client ] && /etc/init.d/modbus_client restart || true); "
                "([ -x /etc/init.d/modbus_server ] && /etc/init.d/modbus_server restart || true)",
                timeout=90.0,
            )
        except TimeoutError:
            # Some RutOS builds apply/restart successfully but their init script
            # does not return promptly. The configuration is already committed,
            # so determine success from a fresh UCI verification instead of
            # falsely reporting the whole deployment as failed.
            _progress(
                progress,
                "Restart is taking longer than expected; verifying committed configuration...",
            )

        _progress(progress, "Verifying live configuration...")
        _verify_committed_config(session)
        _progress(progress, "Deployment complete.")
    except Exception:
        if not committed:
            session.run("uci revert modbus_client || true")
            session.run("uci revert modbus_server || true")
        raise


def rollback_snapshot(
    session: SshSession,
    snapshot: str,
    *,
    progress: ProgressCallback | None = None,
) -> None:
    remote_dir = f"/root/tmc-backups/{snapshot}"
    _progress(progress, "Restoring snapshot files...")
    session.run(
        f"test -f {remote_dir}/modbus_client && "
        f"test -f {remote_dir}/modbus_server && "
        f"cp {remote_dir}/modbus_client /etc/config/modbus_client && "
        f"cp {remote_dir}/modbus_server /etc/config/modbus_server"
    )
    _progress(progress, "Restarting Modbus services...")
    try:
        session.run(
            "([ -x /etc/init.d/modbus_client ] && /etc/init.d/modbus_client restart || true); "
            "([ -x /etc/init.d/modbus_server ] && /etc/init.d/modbus_server restart || true)",
            timeout=90.0,
        )
    except TimeoutError:
        _progress(
            progress,
            "Restart is taking longer than expected; verifying restored configuration...",
        )
    _verify_committed_config(session)
    _progress(progress, "Rollback complete.")
