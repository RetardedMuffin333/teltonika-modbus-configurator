"""Small non-secret desktop preferences shared by live gateway workflows."""

from __future__ import annotations

import json
import os
from pathlib import Path


DEFAULT_GATEWAY_HOST = "10.33.22.1"


def preferences_path() -> Path:
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        base = Path(os.environ["LOCALAPPDATA"]) / "Teltonika Modbus Configurator"
    else:
        base = Path.home() / ".config" / "teltonika-modbus-configurator"
    return base / "preferences.json"


def load_last_gateway_host(*, path: Path | None = None) -> str:
    target = path or preferences_path()
    try:
        value = json.loads(target.read_text(encoding="utf-8")).get("last_gateway_host", "")
    except (OSError, ValueError, TypeError, AttributeError):
        return DEFAULT_GATEWAY_HOST
    return value.strip() if isinstance(value, str) and value.strip() else DEFAULT_GATEWAY_HOST


def save_last_gateway_host(host: str, *, path: Path | None = None) -> None:
    """Persist only the gateway address; credentials are deliberately excluded."""
    value = host.strip()
    if not value:
        return
    target = path or preferences_path()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps({"last_gateway_host": value}, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError:
        # A read-only profile must not block live diagnostics or deployment.
        return
