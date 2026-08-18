"""Load and expand a project definition from YAML."""

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from .models import (
    Device,
    FunctionCode,
    Project,
    Request,
    SerialConnection,
    ServerMapping,
    TcpServerSettings,
)


def _bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    return bool(value)


def _request(item: dict[str, Any]) -> Request:
    return Request(
        name=item["name"],
        function=FunctionCode(int(item["function"])),
        register=int(item["register"]),
        count=int(item.get("count", 1)),
        data_type=str(item.get("data_type", "int16")),
        byte_order=str(item.get("byte_order", "high_byte_first")),
        enabled=_bool(item.get("enabled"), True),
    )


def _format_name(
    pattern: str,
    *,
    device: str,
    index: int,
    ordinal: int,
    request: str = "",
) -> str:
    return pattern.format(
        device=device,
        index=index,
        ordinal=ordinal,
        request=request,
    )


def _expand_groups(data: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Expand reusable templates/device_groups into normal devices and mappings."""
    templates = data.get("templates", {}) or {}
    devices: list[dict[str, Any]] = []
    mappings: list[dict[str, Any]] = []

    for group in data.get("device_groups", []) or []:
        template_name = group["template"]
        if template_name not in templates:
            raise ValueError(f"Unknown template: {template_name}")

        template = templates[template_name] or {}
        count = int(group["count"])
        if count < 1:
            raise ValueError(f"device_group {template_name}: count must be at least 1")

        start_index = int(group.get("start_index", 1))
        name_pattern = str(group.get("name_pattern", "Device{index:02d}"))

        explicit_slave_ids = group.get("slave_ids")
        if explicit_slave_ids is not None:
            slave_ids = [int(x) for x in explicit_slave_ids]
            if len(slave_ids) != count:
                raise ValueError(
                    f"device_group {template_name}: slave_ids length must equal count"
                )
        else:
            slave_start = int(group.get("slave_start", 1))
            slave_step = int(group.get("slave_step", 1))
            slave_ids = [slave_start + n * slave_step for n in range(count)]

        for ordinal in range(count):
            index = start_index + ordinal
            device_name = _format_name(
                name_pattern, device="", index=index, ordinal=ordinal
            )

            devices.append(
                {
                    "name": device_name,
                    "connection": group["connection"],
                    "slave_id": slave_ids[ordinal],
                    "period": group.get("period", template.get("period", 10)),
                    "timeout": group.get("timeout", template.get("timeout", 1)),
                    "enabled": group.get("enabled", template.get("enabled", True)),
                    "requests": deepcopy(template.get("requests", [])),
                }
            )

            for mapping_template in template.get("mappings", []) or []:
                request_name = str(mapping_template["request"])
                mappings.append(
                    {
                        "name": _format_name(
                            str(mapping_template.get("name", "{device}_{request}")),
                            device=device_name,
                            index=index,
                            ordinal=ordinal,
                            request=request_name,
                        ),
                        "device": device_name,
                        "request": request_name,
                        "register_type": mapping_template["register_type"],
                        "register": int(mapping_template["start_register"])
                        + ordinal * int(mapping_template.get("step", 1)),
                        "enabled": mapping_template.get(
                            "enabled", group.get("mapping_enabled", True)
                        ),
                    }
                )

    return devices, mappings


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

    expanded_devices, expanded_mappings = _expand_groups(data)
    raw_devices = list(data.get("devices", []) or []) + expanded_devices
    raw_mappings = list(data.get("mappings", []) or []) + expanded_mappings

    devices = []
    for item in raw_devices:
        requests = [_request(req) for req in item.get("requests", [])]
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
        for item in raw_mappings
    ]

    tcp = data.get("tcp_server", {}) or {}
    tcp_server = TcpServerSettings(
        port=int(tcp.get("port", 502)),
        device_id=int(tcp.get("device_id", 101)),
        enabled=_bool(tcp.get("enabled"), True),
        keep_connection=_bool(tcp.get("keep_connection"), True),
    )

    return Project(
        connections=connections,
        devices=devices,
        mappings=mappings,
        tcp_server=tcp_server,
    )
