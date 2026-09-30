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


@dataclass(slots=True)
class PreflightCheck:
    status: str
    name: str
    detail: str


@dataclass(slots=True)
class GatewayPreflightReport:
    model: str
    firmware: str
    checks: list[PreflightCheck]

    @property
    def errors(self) -> int:
        return sum(check.status == "ERROR" for check in self.checks)

    @property
    def warnings(self) -> int:
        return sum(check.status == "WARNING" for check in self.checks)


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
        deadline = None if effective_timeout <= 0 else monotonic() + effective_timeout
        while not channel.exit_status_ready():
            if deadline is not None and monotonic() >= deadline:
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


def run_gateway_preflight(
    session: SshSession,
    *,
    require_client: bool = True,
    require_server: bool = True,
) -> GatewayPreflightReport:
    """Inspect RutOS Modbus readiness without changing the gateway."""
    import json

    board_text = session.run("ubus call system board 2>/dev/null || echo '{}'")
    try:
        board = json.loads(board_text)
    except (TypeError, ValueError):
        board = {}
    release = board.get("release") if isinstance(board.get("release"), dict) else {}
    model = str(board.get("model") or board.get("board_name") or "Unknown")
    firmware = str(release.get("description") or release.get("version") or "Unknown")

    checks: list[PreflightCheck] = []
    configs = session.run(
        "for f in /etc/config/modbus_client /etc/config/modbus_server; do "
        "[ -f \"$f\" ] && echo \"$f=present\" || echo \"$f=missing\"; done"
    )
    for package in ("modbus_client", "modbus_server"):
        present = f"/etc/config/{package}=present" in configs
        checks.append(PreflightCheck(
            "PASS" if present else "ERROR", f"{package} configuration",
            "/etc/config file is present." if present else "/etc/config file is missing; install/repair the RutOS Modbus package.",
        ))

    init_scripts = session.run(
        "for f in /etc/init.d/modbus_client /etc/init.d/modbus_server; do "
        "[ -x \"$f\" ] && echo \"$f=present\" || echo \"$f=missing\"; done"
    )
    for service in ("modbus_client", "modbus_server"):
        present = f"/etc/init.d/{service}=present" in init_scripts
        checks.append(PreflightCheck(
            "PASS" if present else "ERROR", f"{service} service",
            "Init script is installed." if present else "Init script is missing; the service cannot be managed safely.",
        ))

    client_enabled = session.run(
        "value=$(uci -q get modbus_client.main.enabled); [ -n \"$value\" ] && echo \"$value\" || echo 0"
    ).strip() == "1"
    server_enabled = session.run(
        "value=$(uci -q get modbus_server.modbus.enabled); [ -n \"$value\" ] && echo \"$value\" || echo 0"
    ).strip() == "1"
    for name, enabled, required in (
        ("Modbus Client enabled", client_enabled, require_client),
        ("Modbus TCP Server enabled", server_enabled, require_server),
    ):
        if enabled:
            status, detail = "PASS", "Enabled in UCI."
        elif required:
            status, detail = "ERROR", "Disabled in UCI but required by the current project."
        else:
            status, detail = "INFO", "Disabled in UCI and not required by the current project."
        checks.append(PreflightCheck(status, name, detail))

    runtime = session.run("ubus list 2>/dev/null | grep '^modbus_' || true")
    client_runtime = "modbus_client" in runtime
    server_runtime = "modbus_server" in runtime
    for name, running, enabled in (
        ("Modbus Client runtime", client_runtime, client_enabled),
        ("Modbus Server runtime", server_runtime, server_enabled),
    ):
        if running:
            status, detail = "PASS", "RutOS ubus object is available."
        elif enabled:
            status, detail = "WARNING", "Enabled, but no matching ubus object was found; check service status."
        else:
            status, detail = "INFO", "No runtime object expected while disabled."
        checks.append(PreflightCheck(status, name, detail))

    port_text = session.run(
        "value=$(uci -q get modbus_server.modbus.port); [ -n \"$value\" ] && echo \"$value\" || echo 502"
    ).strip()
    port = int(port_text) if port_text.isdigit() else 502
    listening = session.run(
        f"netstat -lnt 2>/dev/null | grep -q ':{port}[[:space:]]' && echo yes || echo no"
    ).strip() == "yes"
    if listening:
        status, detail = "PASS", f"TCP port {port} is listening."
    elif server_enabled:
        status, detail = "ERROR", f"TCP Server is enabled but port {port} is not listening."
    else:
        status, detail = "INFO", f"Port {port} is not listening while the TCP Server is disabled."
    checks.append(PreflightCheck(status, "Modbus TCP listener", detail))

    webui = session.run(
        "netstat -lnt 2>/dev/null | grep -Eq ':(80|443)[[:space:]]' && echo yes || echo no"
    ).strip() == "yes"
    checks.append(PreflightCheck(
        "PASS" if webui else "WARNING", "RutOS WebUI/API listener",
        "HTTP/HTTPS listener found." if webui else "No port 80/443 listener found; Live Modbus Tester API login may fail.",
    ))

    packages = session.run("opkg list-installed 2>/dev/null | grep -i modbus || true").strip()
    checks.append(PreflightCheck(
        "INFO", "Installed Modbus packages",
        packages.replace("\n", "; ") if packages else "No package names reported by opkg; configuration/service checks above are authoritative.",
    ))
    return GatewayPreflightReport(model=model, firmware=firmware, checks=checks)


def render_gateway_preflight(report: GatewayPreflightReport, *, host: str) -> str:
    lines = [
        "TELTONIKA GATEWAY PREFLIGHT",
        "=" * 30,
        f"Host:     {host}",
        f"Model:    {report.model}",
        f"Firmware: {report.firmware}",
        f"Result:   {report.errors} error(s), {report.warnings} warning(s)",
        "",
    ]
    lines.extend(f"[{check.status:<7}] {check.name}: {check.detail}" for check in report.checks)
    lines.extend([
        "",
        "This check is read-only. It does not install packages, change UCI, or restart services.",
    ])
    return "\n".join(lines) + "\n"


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
    """Verify committed UCI and, when enabled, the live TCP server runtime."""
    session.run("uci export modbus_client >/dev/null")
    session.run("uci export modbus_server >/dev/null")
    enabled = session.run("uci -q get modbus_server.modbus.enabled || true").strip()
    if enabled == "1":
        session.run(
            "ubus list | grep -qx 'modbus_server.modbus' && "
            "netstat -lnt 2>/dev/null | grep -q ':502[[:space:]]'",
            timeout=15.0,
        )


def _restart_modbus_services(session: SshSession) -> None:
    """Restart RutOS Modbus services and let RutOS finish however long it needs."""
    session.run(
        "([ -x /etc/init.d/modbus_client ] && /etc/init.d/modbus_client restart || true); "
        "([ -x /etc/init.d/modbus_server ] && /etc/init.d/modbus_server restart || true)",
        timeout=0,
    )


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

        _progress(progress, "Restarting Modbus services (large configs can take several minutes)...")
        _restart_modbus_services(session)

        _progress(progress, "Verifying live Modbus server...")
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
    _progress(progress, "Restarting Modbus services (large configs can take several minutes)...")
    _restart_modbus_services(session)
    _progress(progress, "Verifying restored Modbus server...")
    _verify_committed_config(session)
    _progress(progress, "Rollback complete.")
