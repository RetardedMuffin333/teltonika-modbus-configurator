"""Safe SSH deployment helpers for RutOS devices."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import unified_diff
from pathlib import Path

import paramiko

from .uci_generator import GeneratedUci


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
    ) -> None:
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

    def run(self, command: str, *, stdin_text: str | None = None) -> str:
        stdin, stdout, stderr = self.client.exec_command(command)
        if stdin_text is not None:
            stdin.write(stdin_text)
            stdin.channel.shutdown_write()
        status = stdout.channel.recv_exit_status()
        output = stdout.read().decode("utf-8", errors="replace")
        error = stderr.read().decode("utf-8", errors="replace")
        if status != 0:
            raise RuntimeError(
                f"Remote command failed ({status}): {command}\n{error.strip()}"
            )
        return output


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


def apply_generated(
    session: SshSession,
    proposed: GeneratedUci,
    *,
    snapshot: str,
) -> None:
    remote_dir = f"/root/tmc-backups/{snapshot}"
    session.run(
        f"mkdir -p {remote_dir} && "
        f"cp /etc/config/modbus_client {remote_dir}/modbus_client && "
        f"cp /etc/config/modbus_server {remote_dir}/modbus_server"
    )

    try:
        session.run("uci import modbus_client", stdin_text=proposed.modbus_client)
        session.run("uci import modbus_server", stdin_text=proposed.modbus_server)

        # Parse/export before commit. If UCI cannot parse the generated package,
        # nothing is committed and the staged changes are reverted below.
        session.run("uci export modbus_client >/dev/null")
        session.run("uci export modbus_server >/dev/null")

        session.run("uci commit modbus_client")
        session.run("uci commit modbus_server")
        session.run(
            "([ -x /etc/init.d/modbus_client ] && /etc/init.d/modbus_client restart || true); "
            "([ -x /etc/init.d/modbus_server ] && /etc/init.d/modbus_server restart || true)"
        )
    except Exception:
        session.run("uci revert modbus_client || true")
        session.run("uci revert modbus_server || true")
        raise


def rollback_snapshot(session: SshSession, snapshot: str) -> None:
    remote_dir = f"/root/tmc-backups/{snapshot}"
    session.run(
        f"test -f {remote_dir}/modbus_client && "
        f"test -f {remote_dir}/modbus_server && "
        f"cp {remote_dir}/modbus_client /etc/config/modbus_client && "
        f"cp {remote_dir}/modbus_server /etc/config/modbus_server"
    )
    session.run(
        "([ -x /etc/init.d/modbus_client ] && /etc/init.d/modbus_client restart || true); "
        "([ -x /etc/init.d/modbus_server ] && /etc/init.d/modbus_server restart || true)"
    )
