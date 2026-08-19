"""Parse RutOS Modbus UCI exports back into the generic project model."""

from __future__ import annotations

from dataclasses import dataclass, field
import shlex

from .models import (
    Device,
    FunctionCode,
    ImportedUciState,
    Project,
    Request,
    SerialConnection,
    ServerMapping,
    TcpServerSettings,
)


REGISTER_TYPES = {"1": "coil", "2": "discrete_input", "3": "holding_register", "4": "input_register"}

# Verified/simple RutOS request datatype tokens. Unknown tokens are preserved raw
# so a live import remains lossless while more byte-order variants are added.
REQUEST_DATA_TYPES = {
    "8bit_int": ("int8", "none"),
    "8bit_uint": ("uint8", "none"),
    "16bit_int_hi_first": ("int16", "high_byte_first"),
    "16bit_int_lo_first": ("int16", "low_byte_first"),
    "16bit_uint_hi_first": ("uint16", "high_byte_first"),
    "16bit_uint_lo_first": ("uint16", "low_byte_first"),
    "ascii": ("ascii", "none"),
    "hex": ("hex", "none"),
    "bool": ("bool", "none"),
    "pdu": ("pdu", "none"),
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
            current = UciSection(parts[1], parts[2]); sections.append(current); continue
        if parts[0] == "option":
            if current is None or len(parts) != 3:
                raise ValueError(f"Invalid option on line {lineno}: {raw}")
            current.options[parts[1]] = parts[2]; continue
        raise ValueError(f"Unsupported UCI directive on line {lineno}: {raw}")
    return sections


def _decode_data_type(value: str) -> tuple[str, str, str | None]:
    decoded = REQUEST_DATA_TYPES.get(value)
    if decoded is not None:
        return decoded[0], decoded[1], None
    return "raw", "raw", value


def import_project(modbus_client: str, modbus_server: str, *, attach_source: bool = True) -> Project:
    """Convert live/exported RutOS Modbus UCI packages to a Project losslessly."""
    client_sections = parse_uci(modbus_client)
    server_sections = parse_uci(modbus_server)

    connection_by_id: dict[str, SerialConnection] = {}
    connections: list[SerialConnection] = []
    for section in client_sections:
        if section.section_type != "rtu_device": continue
        o = section.options
        connection = SerialConnection(
            name=o.get("name", f"RTU_{section.name}"), device=o.get("device", "/dev/rs485"),
            baudrate=int(o.get("baudrate", "19200")), databits=int(o.get("databits", "8")),
            parity=o.get("parity", "none"), stopbits=int(o.get("stopbits", "2")),
        )
        connections.append(connection); connection_by_id[section.name] = connection

    device_section_by_id = {s.name: s for s in client_sections if s.section_type == "rtu_server"}
    tcp_client_ids = {s.name for s in client_sections if s.section_type == "tcp_server"}
    request_sections_by_device: dict[str, list[UciSection]] = {}
    for section in client_sections:
        if section.section_type.startswith("request_"):
            request_sections_by_device.setdefault(section.section_type.removeprefix("request_"), []).append(section)

    tcp_with_requests = sorted(tcp_id for tcp_id in tcp_client_ids if request_sections_by_device.get(tcp_id))
    if tcp_with_requests:
        raise ValueError("Active Modbus TCP Client UCI is present but not modeled yet "
                         f"(tcp_server section(s): {', '.join(tcp_with_requests)}). Import aborted to avoid a lossy round trip.")

    devices: list[Device] = []
    device_name_by_id: dict[str, str] = {}
    request_name_by_key: dict[tuple[str, str], str] = {}

    for device_id, section in device_section_by_id.items():
        o = section.options; connection_id = o.get("rtu_device")
        if connection_id not in connection_by_id:
            raise ValueError(f"RTU server {section.name} references unknown rtu_device {connection_id!r}")
        requests: list[Request] = []
        for req_section in request_sections_by_device.get(device_id, []):
            ro = req_section.options
            token = ro.get("data_type", "16bit_int_hi_first")
            data_type, byte_order, raw_data_type = _decode_data_type(token)
            function = FunctionCode(int(ro["function"]))
            raw_count_values = ro.get("reg_count", "1")
            request_name = ro.get("name", f"Request_{req_section.name}")
            request = Request(
                name=request_name,
                function=function,
                register=int(ro["first_reg"]),
                count=(1 if function.is_write else int(raw_count_values)),
                data_type=data_type,
                byte_order=byte_order,
                enabled=_bool(ro.get("enabled"), True),
                values=(raw_count_values if function.is_write else None),
                raw_data_type=raw_data_type,
            )
            requests.append(request); request_name_by_key[(device_id, req_section.name)] = request_name

        device_name = o.get("name", f"Device_{device_id}")
        devices.append(Device(
            name=device_name, slave_id=int(o["server_id"]), connection=connection_by_id[connection_id].name,
            period=int(o.get("period", "10")), timeout=int(o.get("timeout", "1")),
            enabled=_bool(o.get("enabled"), True), requests=requests,
        ))
        device_name_by_id[device_id] = device_name

    mappings: list[ServerMapping] = []
    tcp_server = TcpServerSettings()
    for section in server_sections:
        o = section.options
        if section.section_type == "modbus":
            tcp_server = TcpServerSettings(
                port=int(o.get("port", "502")), device_id=int(o.get("device_id", "101")),
                enabled=_bool(o.get("enabled"), True), keep_connection=_bool(o.get("keepconn"), True),
            ); continue
        if section.section_type != "tag" or o.get("tag_source") != "modbus_client": continue
        tag_id = o.get("tag_id", ""); parts = tag_id.split(".")
        if len(parts) != 2: raise ValueError(f"Tag {section.name} has invalid tag_id {tag_id!r}")
        device_id, request_id = parts
        if device_id in tcp_client_ids:
            raise ValueError(f"Tag {section.name} references Modbus TCP Client source {tag_id}, which is not modeled yet. Import aborted to avoid data loss.")
        try:
            device_name = device_name_by_id[device_id]; request_name = request_name_by_key[(device_id, request_id)]
        except KeyError as exc:
            raise ValueError(f"Tag {section.name} references unresolved Modbus Client source {tag_id}") from exc
        modbus_type = o.get("modbus_type")
        if modbus_type not in REGISTER_TYPES:
            raise ValueError(f"Tag {section.name} has unsupported modbus_type {modbus_type!r}")
        mappings.append(ServerMapping(
            name=o.get("tag_name", f"Tag_{section.name}"), device=device_name, request=request_name,
            register=int(o["modbus_reg_num"]), register_type=REGISTER_TYPES[modbus_type],
            enabled=_bool(o.get("enabled"), True), permissions=o.get("tag_permissions", "r"),
            data_type=o.get("tag_type", "int16"), count=int(o.get("tag_count", "1")),
        ))

    return Project(
        connections=connections, devices=devices, mappings=mappings, tcp_server=tcp_server,
        source_uci=(ImportedUciState(modbus_client=modbus_client, modbus_server=modbus_server) if attach_source else None),
    )
