from pathlib import Path
import tomllib

from teltonika_modbus_configurator import __version__


def test_pyproject_and_runtime_versions_match():
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["version"] == __version__


def test_release_version_is_0_3_0():
    assert __version__ == "0.3.0"
