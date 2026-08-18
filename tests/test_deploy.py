from pathlib import Path

from teltonika_modbus_configurator.deploy import RemoteConfig, render_diff, save_local_backup
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
