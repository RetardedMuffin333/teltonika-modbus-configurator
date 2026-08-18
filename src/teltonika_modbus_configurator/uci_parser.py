"""Parse RutOS Modbus UCI exports back into the generic project model."""

from __future__ import annotations

from dataclasses import dataclass, field
import shlex

from .models import (
    Device,
    FunctionCode,
    Project,
    Request,
    SerialConnection,
    ServerMapping,
    TcpServerSettings,
)


REGISTER_TYPES = {
    "1": "coil",
    "2": "discrete_input",
    "3": "holding_register",
    "4": "input_register",
}


@dataclass(slots=True)
class UciSection:
    section_type: str
    name: str
    options: dict[str, str] = field(default_factory=dict)


def _bool(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    return value not in {"0", "false", "False", "off"}


def parse_uci(text: str) -> list[UciSection]:
    """Parse the subset of UCI export syntax used by RutOS Modbus packages."""
    sections: list[UciSection] = []
    current: UciSection | None = None

    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("package "):
            continue

        try:
            parts = shlex.split(line, posix=True)
        except ValueError as exc:
            raise ValueError(f"Invalid UCI syntax on line {lineno}: {raw}") from exc

        if not parts:
            continue

        if parts[0] == "config":
            if len(parts) != 3:
                raise ValueError(f"Invalid config declaration on line {lineno}: {raw}")
            current = UciSection(parts[1], parts[2])
            sections.append(current)
            continue

        if parts[0] == "option":
            if current is None or len(parts) != 3:
                raise ValueError(f"Invalid option on line {lineno}: {raw}")
            current.options[parts[1]] = parts[2]
            continue

        # Lists and unsupported directives should not be silently misread.
        raise ValueError(f"Unsupported UCI directive on line {lineno}: {raw}")

    return sections


def _decode_data_type(value: str) -> tuple[str, str]:
    if value == "16bit_int_hi_first":
        return "int16", "high_byte_first"
    if value == "16bit_int_lo_first":
        return "int16", "low_byte_first"
    raise ValueError(f"Unsupported RutOS request data_type: {value}")


def import_project(modbus_client: str, modbus_server: str) -> Project:
    """Convert live/exported RutOS Modbus UCI packages to a Project."""
    client_sections = parse_uci(modbus_client)
    server_sections = parse_uci(modbus_server)

    connection_by_id: dict[str, SerialConnection] = {}
    connections: list[SerialConnection] = []
    for section in client_sections:
        if section.section_type != "rtu_device":
            continue
        o = section.options
        connection = SerialConnection(
            name=o.get("name", f"RTU_{section.name}"),
            device=o.get("device", "/dev/rs485"),
            baudrate=int(o.get("baudrate", "19200")),
            databits=int(o.get("databits", "8")),
            parity=o.get("parity", "none"),
            stopbits=int(o.get("stopbits", "2")),
        )
        connections.append(connection)
        connection_by_id[section.name] = connection

    device_section_by_id: dict[str, UciSection] = {
        s.name: s for s in client_sections if s.section_type == "rtu_server"
    }
    request_sections_by_device: dict[str, list[UciSection]] = {}
    for section in client_sections:
        if section.section_type.startswith("request_"):
            parent_id = section.section_type.removeprefix("request_")
            request_sections_by_device.setdefault(parent_id, []).append(section)

    devices: list[Device] = []
    device_name_by_id: dict[str, str] = {}
    request_name_by_key: dict[tuple[str, str], str] = {}

    for device_id, section in device_section_by_id.items():
        o = section.options
        connection_id = o.get("rtu_device")
        if connection_id not in connection_by_id:
            raise ValueError(
                f"RTU server {section.name} references unknown rtu_device {connection_id!r}"
            )

        requests: list[Request] = []
        for req_section in request_sections_by_device.get(device_id, []):
            ro = req_section.options
            data_type, byte_order = _decode_data_type(
                ro.get("data_type", "16bit_int_hi_first")
            )
            request_name = ro.get("name", f"Request_{req_section.name}")
            request = Request(
                name=request_name,
                function=FunctionCode(int(ro["function"])),
                register=int(ro["first_reg"]),
                count=int(ro.get("reg_count", "1")),
                data_type=data_type,
                byte_order=byte_order,
                enabled=_bool(ro.get("enabled"), True),
            )
            requests.append(request)
            request_name_by_key[(device_id, req_section.name)] = request_name

        device_name = o.get("name", f"Device_{device_id}")
        device = Device(
            name=device_name,
            slave_id=int(o["server_id"]),
            connection=connection_by_id[connection_id].name,
            period=int(o.get("period", "10")),
            timeout=int(o.get("timeout", "1")),
            enabled=_bool(o.get("enabled"), True),
            requests=requests,
        )
        devices.append(device)
        device_name_by_id[device_id] = device_name

    mappings: list[ServerMapping] = []
    tcp_server = TcpServerSettings()

    for section in server_sections:
        o = section.options
        if section.section_type == "modbus":
            tcp_server = TcpServerSettings(
                port=int(o.get("port", "502")),
                device_id=int(o.get("device_id", "101")),
                enabled=_bool(o.get("enabled"), True),
                keep_connection=_bool(o.get("keepconn"), True),
            )
            continue

        if section.section_type != "tag":
            continue
        if o.get("tag_source") != "modbus_client":
            continue

        tag_id = o.get("tag_id", "")
        parts = tag_id.split(".")
        if len(parts) != 2:
            raise ValueError(f"Tag {section.name} has invalid tag_id {tag_id!r}")
        device_id, request_id = parts

        try:
            device_name = device_name_by_id[device_id]
            request_name = request_name_by_key[(device_id, request_id)]
        except KeyError as exc:
            raise ValueError(
                f"Tag {section.name} references unresolved Modbus Client source {tag_id}"
            ) from exc

        modbus_type = o.get("modbus_type")
        if modbus_type not in REGISTER_TYPES:
            raise ValueError(
                f"Tag {section.name} has unsupported modbus_type {modbus_type!r}"
            )

        mappings.append(
            ServerMapping(
                name=o.get("tag_name", f"Tag_{section.name}"),
                device=device_name,
                request=request_name,
                register=int(o["modbus_reg_num"]),
                register_type=REGISTER_TYPES[modbus_type],
                enabled=_bool(o.get("enabled"), True),
            )
        )

    return Project(
        connections=connections,
        devices=devices,
        mappings=mappings,
        tcp_server=tcp_server,
    )
