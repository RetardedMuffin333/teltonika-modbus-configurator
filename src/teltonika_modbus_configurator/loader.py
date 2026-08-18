"""Load a project definition from YAML."""

from pathlib import Path
from typing import Any

import yaml

from .models import Device, FunctionCode, Project, Request, SerialConnection, ServerMapping


def _bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    return bool(value)


def load_project(path: str | Path) -> Project:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}

    connections = []
    for item in data.get("connections", []):
        if item.get("type", "serial") != "serial":
            raise ValueError(f"Unsupported connection type: {item.get('type')}")
        connections.append(
            SerialConnection(
                name=item["name"],
                device=item.get("device", "/dev/rs485"),
                baudrate=int(item.get("baudrate", 19200)),
                databits=int(item.get("databits", 8)),
                parity=str(item.get("parity", "none")),
                stopbits=int(item.get("stopbits", 2)),
            )
        )

    devices = []
    for item in data.get("devices", []):
        requests = []
        for req in item.get("requests", []):
            requests.append(
                Request(
                    name=req["name"],
                    function=FunctionCode(int(req["function"])),
                    register=int(req["register"]),
                    count=int(req.get("count", 1)),
                    data_type=str(req.get("data_type", "int16")),
                    byte_order=str(req.get("byte_order", "high_byte_first")),
                    enabled=_bool(req.get("enabled"), True),
                )
            )
        devices.append(
            Device(
                name=item["name"],
                slave_id=int(item["slave_id"]),
                connection=item["connection"],
                period=int(item.get("period", 10)),
                timeout=int(item.get("timeout", 1)),
                enabled=_bool(item.get("enabled"), True),
                requests=requests,
            )
        )

    mappings = [
        ServerMapping(
            name=item["name"],
            device=item["device"],
            request=item["request"],
            register=int(item["register"]),
            register_type=str(item["register_type"]),
            enabled=_bool(item.get("enabled"), True),
        )
        for item in data.get("mappings", [])
    ]

    return Project(connections=connections, devices=devices, mappings=mappings)
