from pathlib import Path

from teltonika_modbus_configurator.deploy import (
    RemoteConfig,
    apply_generated,
    render_diff,
    save_local_backup,
)
from teltonika_modbus_configurator.uci_generator import GeneratedUci


def test_render_diff_reports_both_packages() -> None:
    current = RemoteConfig(
        modbus_client="package modbus_client\nold\n",
        modbus_server="package modbus_server\nold\n",
    )
    proposed = GeneratedUci(
        modbus_client="package modbus_client\nnew\n",
        modbus_server="package modbus_server\nnew\n",
    )

    diff = render_diff(current, proposed)

    assert "--- live/modbus_client" in diff
    assert "+++ generated/modbus_client" in diff
    assert "--- live/modbus_server" in diff
    assert "+++ generated/modbus_server" in diff
    assert "-old" in diff
    assert "+new" in diff


def test_render_diff_empty_when_configs_match() -> None:
    current = RemoteConfig("client\n", "server\n")
    proposed = GeneratedUci("client\n", "server\n")
    assert render_diff(current, proposed) == ""


def test_save_local_backup(tmp_path: Path) -> None:
    current = RemoteConfig("client config\n", "server config\n")
    target = save_local_backup(current, tmp_path, "snapshot1")

    assert target == tmp_path / "snapshot1"
    assert (target / "modbus_client").read_text() == "client config\n"
    assert (target / "modbus_server").read_text() == "server config\n"


class RecordingSession:
    def __init__(self, *, timeout_restart=False) -> None:
        self.calls = []
        self.timeout_restart = timeout_restart

    def run(self, command, *, stdin_text=None, timeout=None):
        self.calls.append((command, stdin_text, timeout))
        if self.timeout_restart and "modbus_client restart" in command:
            raise TimeoutError("restart still running")
        return ""


def test_apply_generated_reports_stages_and_bounds_restart_wait() -> None:
    session = RecordingSession()
    proposed = GeneratedUci(
        modbus_client="package modbus_client\n",
        modbus_server="package modbus_server\n",
    )
    progress = []

    apply_generated(
        session,
        proposed,
        snapshot="snapshot1",
        progress=progress.append,
    )

    assert progress == [
        "Creating remote backup...",
        "Uploading Modbus Client configuration...",
        "Uploading Modbus Server configuration...",
        "Validating generated UCI...",
        "Committing Modbus configuration...",
        "Restarting Modbus services...",
        "Verifying live configuration...",
        "Deployment complete.",
    ]
    restart_calls = [call for call in session.calls if "modbus_client restart" in call[0]]
    assert len(restart_calls) == 1
    assert restart_calls[0][2] == 90.0


def test_apply_generated_sends_generated_packages_over_stdin() -> None:
    session = RecordingSession()
    proposed = GeneratedUci(
        modbus_client="package modbus_client\nconfig x\n",
        modbus_server="package modbus_server\nconfig y\n",
    )

    apply_generated(session, proposed, snapshot="snapshot2")

    client_import = next(call for call in session.calls if call[0] == "uci import modbus_client")
    server_import = next(call for call in session.calls if call[0] == "uci import modbus_server")
    assert client_import[1] == proposed.modbus_client
    assert server_import[1] == proposed.modbus_server


def test_apply_restart_timeout_is_not_failure_when_committed_config_verifies() -> None:
    session = RecordingSession(timeout_restart=True)
    proposed = GeneratedUci(
        modbus_client="package modbus_client\n",
        modbus_server="package modbus_server\n",
    )
    progress = []

    apply_generated(session, proposed, snapshot="snapshot3", progress=progress.append)

    assert "Restart is taking longer than expected; verifying committed configuration..." in progress
    assert progress[-1] == "Deployment complete."
    revert_calls = [call for call in session.calls if call[0].startswith("uci revert")]
    assert revert_calls == []
    verify_calls = [call for call in session.calls if call[0].startswith("uci export")]
    assert len(verify_calls) >= 4
