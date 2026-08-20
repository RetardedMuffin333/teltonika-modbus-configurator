"""Load and expand a project definition from YAML."""

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from .models import (
    Device,
    FunctionCode,
    ImportedUciState,
    Project,
    Request,
    SerialConnection,
    ServerMapping,
    TcpClientDevice,
    TcpServerSettings,
)


def _bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    return bool(value)


def _request(item: dict[str, Any]) -> Request:
    function = FunctionCode(int(item["function"]))
    values = item.get("values")
    raw = item.get("raw_data_type")
    return Request(
        name=item["name"],
        function=function,
        register=int(item["register"]),
        count=int(item.get("count", 1)),
        data_type=str(item.get("data_type", "int16")),
        byte_order=str(item.get("byte_order", "high_byte_first")),
        enabled=_bool(item.get("enabled"), True),
        values=None if values is None else str(values),
        raw_data_type=None if raw is None else str(raw),
        source_id=None if item.get("source_id") is None else str(item["source_id"]),
    )


def _format_name(pattern: str, *, device: str, index: int, ordinal: int, request: str = "") -> str:
    return pattern.format(device=device, index=index, ordinal=ordinal, request=request)


def _expand_groups(data: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    templates = data.get("templates", {}) or {}
    devices = []
    mappings = []
    for group in data.get("device_groups", []) or []:
        template_name = group["template"]
        if template_name not in templates:
            raise ValueError(f"Unknown template: {template_name}")
        template = templates[template_name] or {}
        count = int(group["count"])
        if count < 1:
            raise ValueError(f"device_group {template_name}: count must be at least 1")
        start_index = int(group.get("start_index", 1))
        pattern = str(group.get("name_pattern", "Device{index:02d}"))
        if group.get("slave_ids") is not None:
            slave_ids = [int(x) for x in group["slave_ids"]]
            if len(slave_ids) != count:
                raise ValueError(f"device_group {template_name}: slave_ids length must equal count")
        else:
            start = int(group.get("slave_start", 1))
            step = int(group.get("slave_step", 1))
            slave_ids = [start + n * step for n in range(count)]
        for ordinal in range(count):
            index = start_index + ordinal
            name = _format_name(pattern, device="", index=index, ordinal=ordinal)
            devices.append({
                "name": name,
                "connection": group["connection"],
                "slave_id": slave_ids[ordinal],
                "period": group.get("period", template.get("period", 10)),
                "timeout": group.get("timeout", template.get("timeout", 1)),
                "enabled": group.get("enabled", template.get("enabled", True)),
                "requests": deepcopy(template.get("requests", [])),
            })
            for mt in template.get("mappings", []) or []:
                rn = str(mt["request"])
                mappings.append({
                    "name": _format_name(str(mt.get("name", "{device}_{request}")), device=name, index=index, ordinal=ordinal, request=rn),
                    "device": name,
                    "request": rn,
                    "register_type": mt["register_type"],
                    "register": int(mt["start_register"]) + ordinal * int(mt.get("step", 1)),
                    "enabled": mt.get("enabled", group.get("mapping_enabled", True)),
                    "permissions": mt.get("permissions", "r"),
                    "data_type": mt.get("data_type", "int16"),
                    "count": mt.get("count", 1),
                })
    return devices, mappings


def load_project(path: str | Path) -> Project:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}

    connections = []
    for i in data.get("connections", []):
        if i.get("type", "serial") != "serial":
            raise ValueError(f"Unsupported connection type: {i.get('type')}")
        connections.append(SerialConnection(
            name=i["name"],
            device=i.get("device", "/dev/rs485"),
            baudrate=int(i.get("baudrate", 19200)),
            databits=int(i.get("databits", 8)),
            parity=str(i.get("parity", "none")),
            stopbits=int(i.get("stopbits", 2)),
            source_id=None if i.get("source_id") is None else str(i["source_id"]),
        ))

    expanded_devices, expanded_mappings = _expand_groups(data)
    raw_devices = list(data.get("devices", []) or []) + expanded_devices
    raw_mappings = list(data.get("mappings", []) or []) + expanded_mappings

    devices = [Device(
        name=i["name"],
        slave_id=int(i["slave_id"]),
        connection=i["connection"],
        period=int(i.get("period", 10)),
        timeout=int(i.get("timeout", 1)),
        enabled=_bool(i.get("enabled"), True),
        requests=[_request(r) for r in i.get("requests", [])],
        source_id=None if i.get("source_id") is None else str(i["source_id"]),
    ) for i in raw_devices]

    tcp_clients = [TcpClientDevice(
        name=i["name"],
        server_id=int(i.get("server_id", 1)),
        host=str(i.get("host", "")),
        port=int(i.get("port", 502)),
        period=int(i.get("period", 60)),
        timeout=int(i.get("timeout", 5)),
        enabled=_bool(i.get("enabled"), True),
        requests=[_request(r) for r in i.get("requests", [])],
        source_id=None if i.get("source_id") is None else str(i["source_id"]),
        raw_options={str(k): str(v) for k, v in (i.get("raw_options", {}) or {}).items()},
    ) for i in data.get("tcp_clients", []) or []]

    mappings = [ServerMapping(
        name=i["name"],
        device=i["device"],
        request=i["request"],
        register=int(i["register"]),
        register_type=str(i["register_type"]),
        enabled=_bool(i.get("enabled"), True),
        permissions=str(i.get("permissions", "r")),
        data_type=str(i.get("data_type", "int16")),
        count=int(i.get("count", 1)),
        source_id=None if i.get("source_id") is None else str(i["source_id"]),
    ) for i in raw_mappings]

    tcp = data.get("tcp_server", {}) or {}
    tcp_server = TcpServerSettings(
        port=int(tcp.get("port", 502)),
        device_id=int(tcp.get("device_id", 101)),
        enabled=_bool(tcp.get("enabled"), True),
        keep_connection=_bool(tcp.get("keep_connection"), True),
    )

    source = data.get("source_uci") or None
    source_uci = ImportedUciState(
        modbus_client=str(source["modbus_client"]),
        modbus_server=str(source["modbus_server"]),
    ) if source else None

    return Project(
        connections=connections,
        devices=devices,
        tcp_clients=tcp_clients,
        mappings=mappings,
        tcp_server=tcp_server,
        source_uci=source_uci,
    )
