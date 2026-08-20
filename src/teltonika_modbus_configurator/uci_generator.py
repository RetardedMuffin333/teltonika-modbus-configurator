"""Generate RutOS UCI packages from the generic project model."""

from dataclasses import dataclass
import re

from .models import Project, Request
from .validator import raise_for_errors, validate_project

REGISTER_TYPES = {"coil": "1", "discrete_input": "2", "holding_register": "3", "input_register": "4"}
REQUEST_DATA_TYPES = {
    ("int8", "none"): "8bit_int", ("uint8", "none"): "8bit_uint",
    ("int16", "high_byte_first"): "16bit_int_hi_first", ("int16", "low_byte_first"): "16bit_int_lo_first",
    ("uint16", "high_byte_first"): "16bit_uint_hi_first", ("uint16", "low_byte_first"): "16bit_uint_lo_first",
    ("ascii", "none"): "ascii", ("hex", "none"): "hex", ("bool", "none"): "bool", ("pdu", "none"): "pdu",
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


def _request_options(request: Request) -> dict[str, str]:
    return {
        "name": request.name,
        "enabled": _on(request.enabled),
        "function": str(int(request.function)),
        "data_type": _request_data_type(request),
        "reg_count": request.count_or_values,
        "store_on_change_only": "0",
        "first_reg": str(request.register),
        "no_brackets": "0",
        "broadcast": "0",
    }


def _mapping_options(mapping, source_device_id: int | str, source_request_id: int | str) -> dict[str, str]:
    return {
        "modbus_dev_config": "modbus",
        "tag_name": mapping.name,
        "tag_source": "modbus_client",
        "tag_permissions": mapping.permissions,
        "tag_start": "0",
        "modbus_reg_num": str(mapping.register),
        "modbus_type": REGISTER_TYPES[mapping.register_type],
        "tag_id": f"{source_device_id}.{source_request_id}",
        "enabled": _on(mapping.enabled),
        "tag_type": mapping.data_type,
        "tag_count": str(mapping.count),
    }


def _section(section_type: str, section_id: int | str, options: dict[str, str]) -> str:
    lines = [f"config {section_type} {_q(section_id)}"]
    lines.extend(f"\toption {key} {_q(value)}" for key, value in options.items())
    return "\n".join(lines)


def _request_section(device_id: int | str, request_id: int | str, request: Request) -> str:
    return _section(f"request_{device_id}", request_id, _request_options(request))


def _mapping_section(tag_id: int | str, mapping, source_device_id: int | str, source_request_id: int | str) -> str:
    return _section("tag", tag_id, _mapping_options(mapping, source_device_id, source_request_id))


def _numeric_max(sections) -> int:
    return max([int(s.name) for s in sections if s.name.isdigit()], default=0)


_CONFIG_RE = re.compile(r"^\s*config\s+(\S+)\s+['\"]?([^'\"\s]+)['\"]?\s*$")
_OPTION_RE = re.compile(r"^(\s*)option\s+(\S+)\s+.*$")


def _split_blocks(text: str) -> tuple[str, list[tuple[tuple[str, str], str]]]:
    lines = text.splitlines(keepends=True)
    starts = []
    for i, raw in enumerate(lines):
        m = _CONFIG_RE.match(raw.rstrip("\r\n"))
        if m:
            starts.append((i, (m.group(1), m.group(2))))
    if not starts:
        return text, []
    preamble = "".join(lines[:starts[0][0]])
    blocks = []
    for n, (start, key) in enumerate(starts):
        end = starts[n + 1][0] if n + 1 < len(starts) else len(lines)
        blocks.append((key, "".join(lines[start:end])))
    return preamble, blocks


def _patch_options(block: str, options: dict[str, str]) -> str:
    lines = block.splitlines()
    seen = set()
    for i in range(1, len(lines)):
        m = _OPTION_RE.match(lines[i])
        if not m:
            continue
        key = m.group(2)
        if key in options:
            lines[i] = f"{m.group(1)}option {key} {_q(options[key])}"
            seen.add(key)
    for key, value in options.items():
        if key not in seen:
            lines.append(f"\toption {key} {_q(value)}")
    return "\n".join(lines).rstrip("\n") + "\n\n"


def _rewrite_package(original: str, replacements: dict[tuple[str, str], dict[str, str]], deletions: set[tuple[str, str]], additions: list[str]) -> str:
    preamble, blocks = _split_blocks(original)
    out = preamble
    for key, raw in blocks:
        if key in deletions:
            continue
        out += _patch_options(raw, replacements[key]) if key in replacements else raw
    if additions:
        if out and not out.endswith("\n\n"):
            out = out.rstrip("\n") + "\n\n"
        out += "\n\n".join(a.rstrip("\n") for a in additions) + "\n"
    return out


def _generate_from_imported(project: Project) -> GeneratedUci:
    from .uci_parser import import_project, parse_uci

    source = project.source_uci
    assert source is not None
    baseline = import_project(source.modbus_client, source.modbus_server, attach_source=False)

    if (
        project.connections == baseline.connections
        and project.devices == baseline.devices
        and project.tcp_clients == baseline.tcp_clients
        and project.mappings == baseline.mappings
        and project.tcp_server == baseline.tcp_server
    ):
        return GeneratedUci(source.modbus_client, source.modbus_server)

    # v0.3 foundation makes existing TCP Client sections first-class and lossless,
    # but does not yet rewrite/create them until their exact RutOS UCI options are
    # captured from real hardware. RTU and TCP Server mappings may still be edited.
    if project.tcp_clients != baseline.tcp_clients:
        raise ValueError(
            "Modbus TCP Client devices are imported losslessly in the v0.3 foundation, "
            "but editing/creating TCP Client device sections is not enabled until a live RutOS UCI sample is verified."
        )

    client_sections = parse_uci(source.modbus_client)
    server_sections = parse_uci(source.modbus_server)
    next_id = _numeric_max(client_sections) + 1
    next_tag = _numeric_max([s for s in server_sections if s.section_type == "tag"]) + 1
    client_repl = {}
    server_repl = {}
    client_del = set()
    server_del = set()
    client_add = []
    server_add = []

    connection_ids: dict[str, str] = {}
    for c in project.connections:
        if c.source_id is None:
            cid = str(next_id)
            next_id += 1
            client_add.append(_section("rtu_device", cid, {
                "full_duplex_enabled": "0", "device": c.device, "baudrate": str(c.baudrate),
                "flowcontrol": "none", "databits": str(c.databits), "parity": c.parity,
                "name": c.name, "stopbits": str(c.stopbits), "enabled": "1",
            }))
        else:
            cid = c.source_id
            client_repl[("rtu_device", cid)] = {
                "device": c.device, "baudrate": str(c.baudrate), "databits": str(c.databits),
                "parity": c.parity, "name": c.name, "stopbits": str(c.stopbits),
            }
        connection_ids[c.name] = cid

    current_conn_ids = {c.source_id for c in project.connections if c.source_id is not None}
    for c in baseline.connections:
        if c.source_id not in current_conn_ids:
            client_del.add(("rtu_device", str(c.source_id)))

    device_ids: dict[str, str] = {}
    request_ids: dict[tuple[str, str], str] = {}

    for d in project.devices:
        if d.connection not in connection_ids:
            raise ValueError(f"Device {d.name!r} references unresolved connection {d.connection!r}")
        if d.source_id is None:
            did = str(next_id)
            next_id += 1
            client_add.append(_section("rtu_server", did, {
                "server_id": str(d.slave_id), "rtu_device": connection_ids[d.connection],
                "skip_on_many_tmos": "0", "timeout": str(d.timeout), "period": str(d.period),
                "frequency": "period", "name": d.name, "enabled": _on(d.enabled),
            }))
        else:
            did = d.source_id
            client_repl[("rtu_server", did)] = {
                "server_id": str(d.slave_id), "rtu_device": connection_ids[d.connection],
                "timeout": str(d.timeout), "period": str(d.period), "name": d.name, "enabled": _on(d.enabled),
            }
        device_ids[d.name] = did
        for r in d.requests:
            if r.source_id is None:
                rid = str(next_id)
                next_id += 1
                client_add.append(_request_section(did, rid, r))
            else:
                rid = r.source_id
                client_repl[(f"request_{did}", rid)] = _request_options(r)
            request_ids[(d.name, r.name)] = rid

    # Existing TCP Client sections are not rewritten yet, but their stable source
    # IDs participate in tag_id resolution so mixed RTU + TCP projects can safely
    # edit the surrounding Modbus TCP Server configuration.
    for d in project.tcp_clients:
        if d.source_id is None:
            raise ValueError("Fresh Modbus TCP Client generation is not enabled in the v0.3 foundation yet")
        did = d.source_id
        device_ids[d.name] = did
        for r in d.requests:
            if r.source_id is None:
                raise ValueError("Adding requests to Modbus TCP Client devices is not enabled until live UCI is verified")
            request_ids[(d.name, r.name)] = r.source_id

    current_device_ids = {d.source_id for d in project.devices if d.source_id is not None}
    current_request_ids = {r.source_id for d in project.devices for r in d.requests if r.source_id is not None}
    for d in baseline.devices:
        if d.source_id not in current_device_ids:
            client_del.add(("rtu_server", str(d.source_id)))
            for r in d.requests:
                client_del.add((f"request_{d.source_id}", str(r.source_id)))
        else:
            for r in d.requests:
                if r.source_id not in current_request_ids:
                    client_del.add((f"request_{d.source_id}", str(r.source_id)))

    server_repl[("modbus", "modbus")] = {
        "keepconn": _on(project.tcp_server.keep_connection),
        "port": str(project.tcp_server.port),
        "device_id": str(project.tcp_server.device_id),
        "enabled": _on(project.tcp_server.enabled),
    }

    for m in project.mappings:
        key = (m.device, m.request)
        if m.device not in device_ids or key not in request_ids:
            raise ValueError(f"Mapping {m.name!r} references unresolved source {m.device}/{m.request}")
        opts = _mapping_options(m, device_ids[m.device], request_ids[key])
        if m.source_id is None:
            tid = str(next_tag)
            next_tag += 1
            server_add.append(_section("tag", tid, opts))
        else:
            server_repl[("tag", m.source_id)] = opts

    current_mapping_ids = {m.source_id for m in project.mappings if m.source_id is not None}
    for m in baseline.mappings:
        if m.source_id not in current_mapping_ids:
            server_del.add(("tag", str(m.source_id)))

    return GeneratedUci(
        _rewrite_package(source.modbus_client, client_repl, client_del, client_add),
        _rewrite_package(source.modbus_server, server_repl, server_del, server_add),
    )


def _generate_fresh(project: Project) -> GeneratedUci:
    if project.tcp_clients:
        raise ValueError(
            "Fresh Modbus TCP Client generation is not enabled in the v0.3 foundation yet; "
            "import one live TCP Client example first so its exact RutOS UCI schema can be verified."
        )

    client = ["package modbus_client", "", "config main 'main'", "\toption debug '0'", "\toption enabled '1'", ""]
    next_id = 1
    connection_ids = {}
    device_ids = {}
    request_ids = {}

    for c in project.connections:
        cid = next_id
        next_id += 1
        connection_ids[c.name] = cid
        client.extend(_section("rtu_device", cid, {
            "full_duplex_enabled": "0", "device": c.device, "baudrate": str(c.baudrate),
            "flowcontrol": "none", "databits": str(c.databits), "parity": c.parity,
            "name": c.name, "stopbits": str(c.stopbits), "enabled": "1",
        }).splitlines() + [""])

    for d in project.devices:
        did = next_id
        next_id += 1
        device_ids[d.name] = did
        client.extend(_section("rtu_server", did, {
            "server_id": str(d.slave_id), "rtu_device": str(connection_ids[d.connection]),
            "skip_on_many_tmos": "0", "timeout": str(d.timeout), "period": str(d.period),
            "frequency": "period", "name": d.name, "enabled": _on(d.enabled),
        }).splitlines() + [""])
        for r in d.requests:
            rid = next_id
            next_id += 1
            request_ids[(d.name, r.name)] = rid
            client.extend(_request_section(did, rid, r).splitlines() + [""])

    t = project.tcp_server
    server = [
        "package modbus_server", "", "config modbus 'modbus'",
        f"\toption keepconn {_q(_on(t.keep_connection))}", "\toption timeout '0'",
        f"\toption port {_q(t.port)}", "\toption md_data_type '0'", "\toption clientregs '0'",
        "\toption broadcasts '0'", f"\toption device_id {_q(t.device_id)}",
        f"\toption enabled {_q(_on(t.enabled))}", "",
    ]
    for tid, m in enumerate(project.mappings, start=1):
        server.extend(_mapping_section(tid, m, device_ids[m.device], request_ids[(m.device, m.request)]).splitlines() + [""])
    return GeneratedUci("\n".join(client).rstrip() + "\n", "\n".join(server).rstrip() + "\n")


def generate_uci(project: Project) -> GeneratedUci:
    messages = validate_project(project)
    raise_for_errors(messages)
    return _generate_from_imported(project) if project.source_uci is not None else _generate_fresh(project)
