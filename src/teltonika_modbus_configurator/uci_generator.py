"""Generate RutOS UCI packages from the generic project model."""

from dataclasses import dataclass

from .models import Project, Request
from .validator import raise_for_errors, validate_project

REGISTER_TYPES = {"coil": "1", "discrete_input": "2", "holding_register": "3", "input_register": "4"}
REQUEST_DATA_TYPES = {
    ("int8", "none"): "8bit_int",
    ("uint8", "none"): "8bit_uint",
    ("int16", "high_byte_first"): "16bit_int_hi_first",
    ("int16", "low_byte_first"): "16bit_int_lo_first",
    ("uint16", "high_byte_first"): "16bit_uint_hi_first",
    ("uint16", "low_byte_first"): "16bit_uint_lo_first",
    ("ascii", "none"): "ascii",
    ("hex", "none"): "hex",
    ("bool", "none"): "bool",
    ("pdu", "none"): "pdu",
}

@dataclass(slots=True)
class GeneratedUci:
    modbus_client: str
    modbus_server: str


def _q(value: object) -> str:
    return "'" + str(value).replace("'", "'\\''") + "'"


def _on(value: bool) -> str:
    return "1" if value else "0"


def _request_data_type(request: Request) -> str:
    if request.raw_data_type:
        return request.raw_data_type
    try:
        return REQUEST_DATA_TYPES[(request.data_type, request.byte_order)]
    except KeyError as exc:
        raise ValueError(f"Unsupported datatype/byte order for {request.name}: {request.data_type}/{request.byte_order}") from exc


def _request_section(device_id: int | str, request_id: int | str, request: Request) -> str:
    return "\n".join([
        f"config request_{device_id} {_q(request_id)}",
        f"\toption name {_q(request.name)}",
        f"\toption enabled {_q(_on(request.enabled))}",
        f"\toption function {_q(int(request.function))}",
        f"\toption data_type {_q(_request_data_type(request))}",
        f"\toption reg_count {_q(request.count_or_values)}",
        "\toption store_on_change_only '0'",
        f"\toption first_reg {_q(request.register)}",
        "\toption no_brackets '0'",
        "\toption broadcast '0'",
    ])


def _mapping_section(tag_id: int | str, mapping, source_device_id: int | str, source_request_id: int | str) -> str:
    modbus_type = REGISTER_TYPES[mapping.register_type]
    return "\n".join([
        f"config tag {_q(tag_id)}",
        "\toption modbus_dev_config 'modbus'",
        f"\toption tag_name {_q(mapping.name)}",
        "\toption tag_source 'modbus_client'",
        f"\toption tag_permissions {_q(mapping.permissions)}",
        "\toption tag_start '0'",
        f"\toption modbus_reg_num {_q(mapping.register)}",
        f"\toption modbus_type {_q(modbus_type)}",
        f"\toption tag_id {_q(f'{source_device_id}.{source_request_id}')}",
        f"\toption enabled {_q(_on(mapping.enabled))}",
        f"\toption tag_type {_q(mapping.data_type)}",
        f"\toption tag_count {_q(mapping.count)}",
    ])


def _append_sections(original: str, sections: list[str]) -> str:
    if not sections:
        return original
    return original.rstrip("\n") + "\n\n" + "\n\n".join(s.rstrip("\n") for s in sections) + "\n"


def _numeric_max(sections) -> int:
    return max([int(s.name) for s in sections if s.name.isdigit()], default=0)


def _generate_from_imported(project: Project) -> GeneratedUci:
    from .uci_parser import import_project, parse_uci
    source = project.source_uci
    assert source is not None
    baseline = import_project(source.modbus_client, source.modbus_server, attach_source=False)
    bc = {c.name: c for c in baseline.connections}; cc = {c.name: c for c in project.connections}
    bd = {d.name: d for d in baseline.devices}; cd = {d.name: d for d in project.devices}
    bm = {m.name: m for m in baseline.mappings}; cm = {m.name: m for m in project.mappings}
    for name, item in bc.items():
        if name not in cc or cc[name] != item: raise ValueError(f"Imported connection {name!r} was removed/edited. Live deployment is append-only.")
    for name, item in bd.items():
        if name not in cd or cd[name] != item: raise ValueError(f"Imported device {name!r} or its requests were removed/edited. Live deployment is append-only.")
    for name, item in bm.items():
        if name not in cm or cm[name] != item: raise ValueError(f"Imported TCP mapping {name!r} was removed/edited. Live deployment is append-only.")
    if project.tcp_server != baseline.tcp_server: raise ValueError("Imported TCP Server settings were edited. Live deployment is append-only.")
    new_connections = [c for c in project.connections if c.name not in bc]
    new_devices = [d for d in project.devices if d.name not in bd]
    new_mappings = [m for m in project.mappings if m.name not in bm]
    if not new_connections and not new_devices and not new_mappings:
        return GeneratedUci(source.modbus_client, source.modbus_server)

    client_sections = parse_uci(source.modbus_client); server_sections = parse_uci(source.modbus_server)
    next_id = _numeric_max(client_sections) + 1
    connection_ids = {s.options.get("name", f"RTU_{s.name}"): s.name for s in client_sections if s.section_type == "rtu_device"}
    device_ids = {s.options.get("name", f"Device_{s.name}"): s.name for s in client_sections if s.section_type == "rtu_server"}
    request_ids: dict[tuple[str, str], int | str] = {}
    for s in client_sections:
        if s.section_type.startswith("request_"):
            pid = s.section_type.removeprefix("request_")
            pname = next((n for n, ident in device_ids.items() if str(ident) == pid), None)
            if pname is not None: request_ids[(pname, s.options.get("name", f"Request_{s.name}"))] = s.name

    add_client: list[str] = []
    for c in new_connections:
        cid = next_id; next_id += 1; connection_ids[c.name] = cid
        add_client.append("\n".join([f"config rtu_device {_q(cid)}", "\toption full_duplex_enabled '0'", f"\toption device {_q(c.device)}", f"\toption baudrate {_q(c.baudrate)}", "\toption flowcontrol 'none'", f"\toption databits {_q(c.databits)}", f"\toption parity {_q(c.parity)}", f"\toption name {_q(c.name)}", f"\toption stopbits {_q(c.stopbits)}", "\toption enabled '1'"]))
    for d in new_devices:
        did = next_id; next_id += 1; device_ids[d.name] = did
        add_client.append("\n".join([f"config rtu_server {_q(did)}", f"\toption server_id {_q(d.slave_id)}", f"\toption rtu_device {_q(connection_ids[d.connection])}", "\toption skip_on_many_tmos '0'", f"\toption timeout {_q(d.timeout)}", f"\toption period {_q(d.period)}", "\toption frequency 'period'", f"\toption name {_q(d.name)}", f"\toption enabled {_q(_on(d.enabled))}"]))
        for r in d.requests:
            rid = next_id; next_id += 1; request_ids[(d.name, r.name)] = rid; add_client.append(_request_section(did, rid, r))

    next_tag = _numeric_max([s for s in server_sections if s.section_type == "tag"]) + 1
    add_server: list[str] = []
    for m in new_mappings:
        key = (m.device, m.request)
        if m.device not in device_ids or key not in request_ids: raise ValueError(f"Mapping {m.name!r} references unresolved source {m.device}/{m.request}")
        add_server.append(_mapping_section(next_tag, m, device_ids[m.device], request_ids[key])); next_tag += 1
    return GeneratedUci(_append_sections(source.modbus_client, add_client), _append_sections(source.modbus_server, add_server))


def _generate_fresh(project: Project) -> GeneratedUci:
    client = ["package modbus_client", "", "config main 'main'", "\toption debug '0'", "\toption enabled '1'", ""]
    next_id = 1; connection_ids = {}; device_ids = {}; request_ids = {}
    for c in project.connections:
        cid = next_id; next_id += 1; connection_ids[c.name] = cid
        client.extend([f"config rtu_device {_q(cid)}", "\toption full_duplex_enabled '0'", f"\toption device {_q(c.device)}", f"\toption baudrate {_q(c.baudrate)}", "\toption flowcontrol 'none'", f"\toption databits {_q(c.databits)}", f"\toption parity {_q(c.parity)}", f"\toption name {_q(c.name)}", f"\toption stopbits {_q(c.stopbits)}", "\toption enabled '1'", ""])
    for d in project.devices:
        did = next_id; next_id += 1; device_ids[d.name] = did
        client.extend([f"config rtu_server {_q(did)}", f"\toption server_id {_q(d.slave_id)}", f"\toption rtu_device {_q(connection_ids[d.connection])}", "\toption skip_on_many_tmos '0'", f"\toption timeout {_q(d.timeout)}", f"\toption period {_q(d.period)}", "\toption frequency 'period'", f"\toption name {_q(d.name)}", f"\toption enabled {_q(_on(d.enabled))}", ""])
        for r in d.requests:
            rid = next_id; next_id += 1; request_ids[(d.name, r.name)] = rid; client.extend(_request_section(did, rid, r).splitlines() + [""])
    t = project.tcp_server
    server = ["package modbus_server", "", "config modbus 'modbus'", f"\toption keepconn {_q(_on(t.keep_connection))}", "\toption timeout '0'", f"\toption port {_q(t.port)}", "\toption md_data_type '0'", "\toption clientregs '0'", "\toption broadcasts '0'", f"\toption device_id {_q(t.device_id)}", f"\toption enabled {_q(_on(t.enabled))}", ""]
    for tid, m in enumerate(project.mappings, start=1):
        server.extend(_mapping_section(tid, m, device_ids[m.device], request_ids[(m.device, m.request)]).splitlines() + [""])
    return GeneratedUci("\n".join(client).rstrip() + "\n", "\n".join(server).rstrip() + "\n")


def generate_uci(project: Project) -> GeneratedUci:
    messages = validate_project(project); raise_for_errors(messages)
    return _generate_from_imported(project) if project.source_uci is not None else _generate_fresh(project)
