"""Generate RutOS UCI packages from the generic project model."""

from dataclasses import dataclass

from .models import Project, Request
from .validator import raise_for_errors, validate_project


REGISTER_TYPES = {
    "coil": "1",
    "discrete_input": "2",
    "holding_register": "3",
    "input_register": "4",
}


@dataclass(slots=True)
class GeneratedUci:
    modbus_client: str
    modbus_server: str


def _q(value: object) -> str:
    text = str(value).replace("'", "'\\''")
    return f"'{text}'"


def _on(value: bool) -> str:
    return "1" if value else "0"


def _request_data_type(request: Request) -> str:
    if request.data_type == "int16" and request.byte_order == "high_byte_first":
        return "16bit_int_hi_first"
    if request.data_type == "int16" and request.byte_order == "low_byte_first":
        return "16bit_int_lo_first"
    raise ValueError(
        f"Unsupported datatype/byte order for {request.name}: "
        f"{request.data_type}/{request.byte_order}"
    )


def _append_sections(original: str, sections: list[str]) -> str:
    if not sections:
        return original
    base = original.rstrip("\n")
    addition = "\n\n".join(section.rstrip("\n") for section in sections)
    return f"{base}\n\n{addition}\n"


def _numeric_max(sections) -> int:
    values = [int(s.name) for s in sections if s.name.isdigit()]
    return max(values, default=0)


def _generate_from_imported(project: Project) -> GeneratedUci:
    """Generate an append-only update on top of an imported live baseline.

    v1 deliberately refuses edits/deletions of imported entities. This keeps the
    original RutOS UCI byte-for-byte intact and assigns new IDs only to new
    entities. It makes live-import -> zero edits a guaranteed zero diff while
    still supporting the main v1 workflow: add new RTU devices and TCP mappings.
    """
    from .uci_parser import import_project, parse_uci

    source = project.source_uci
    assert source is not None
    baseline = import_project(
        source.modbus_client,
        source.modbus_server,
        attach_source=False,
    )

    baseline_connections = {c.name: c for c in baseline.connections}
    current_connections = {c.name: c for c in project.connections}
    baseline_devices = {d.name: d for d in baseline.devices}
    current_devices = {d.name: d for d in project.devices}
    baseline_mappings = {m.name: m for m in baseline.mappings}
    current_mappings = {m.name: m for m in project.mappings}

    for name, item in baseline_connections.items():
        if name not in current_connections:
            raise ValueError(
                f"Imported connection {name!r} was removed. v1 live deployment is append-only; "
                "re-import the TRB or restore the original item."
            )
        if current_connections[name] != item:
            raise ValueError(
                f"Imported connection {name!r} was edited. v1 live deployment currently preserves "
                "imported entities exactly and supports additions only."
            )

    for name, item in baseline_devices.items():
        if name not in current_devices:
            raise ValueError(
                f"Imported device {name!r} was removed. v1 live deployment is append-only."
            )
        if current_devices[name] != item:
            raise ValueError(
                f"Imported device {name!r} or one of its requests was edited. v1 live deployment "
                "currently supports additions only."
            )

    for name, item in baseline_mappings.items():
        if name not in current_mappings:
            raise ValueError(
                f"Imported TCP mapping {name!r} was removed. v1 live deployment is append-only."
            )
        if current_mappings[name] != item:
            raise ValueError(
                f"Imported TCP mapping {name!r} was edited. v1 live deployment currently supports "
                "additions only."
            )

    if project.tcp_server != baseline.tcp_server:
        raise ValueError(
            "Imported TCP Server settings were edited. v1 live deployment currently preserves "
            "the imported server settings exactly and supports additions only."
        )

    new_connections = [c for c in project.connections if c.name not in baseline_connections]
    new_devices = [d for d in project.devices if d.name not in baseline_devices]
    new_mappings = [m for m in project.mappings if m.name not in baseline_mappings]

    if not new_connections and not new_devices and not new_mappings:
        return GeneratedUci(source.modbus_client, source.modbus_server)

    client_sections = parse_uci(source.modbus_client)
    server_sections = parse_uci(source.modbus_server)
    next_id = _numeric_max(client_sections) + 1

    connection_ids: dict[str, int | str] = {}
    for section in client_sections:
        if section.section_type == "rtu_device":
            name = section.options.get("name", f"RTU_{section.name}")
            connection_ids[name] = section.name

    device_ids: dict[str, int | str] = {}
    request_ids: dict[tuple[str, str], int | str] = {}
    for section in client_sections:
        if section.section_type == "rtu_server":
            name = section.options.get("name", f"Device_{section.name}")
            device_ids[name] = section.name
    for section in client_sections:
        if section.section_type.startswith("request_"):
            parent_id = section.section_type.removeprefix("request_")
            parent_name = next(
                (name for name, ident in device_ids.items() if str(ident) == parent_id),
                None,
            )
            if parent_name is not None:
                req_name = section.options.get("name", f"Request_{section.name}")
                request_ids[(parent_name, req_name)] = section.name

    additions_client: list[str] = []

    for connection in new_connections:
        connection_id = next_id
        next_id += 1
        connection_ids[connection.name] = connection_id
        additions_client.append(
            "\n".join(
                [
                    f"config rtu_device {_q(connection_id)}",
                    "\toption full_duplex_enabled '0'",
                    f"\toption device {_q(connection.device)}",
                    f"\toption baudrate {_q(connection.baudrate)}",
                    "\toption flowcontrol 'none'",
                    f"\toption databits {_q(connection.databits)}",
                    f"\toption parity {_q(connection.parity)}",
                    f"\toption name {_q(connection.name)}",
                    f"\toption stopbits {_q(connection.stopbits)}",
                    "\toption enabled '1'",
                ]
            )
        )

    for device in new_devices:
        if device.connection not in connection_ids:
            raise ValueError(
                f"New device {device.name!r} references connection {device.connection!r}, "
                "which has no imported or newly generated UCI section."
            )
        device_id = next_id
        next_id += 1
        device_ids[device.name] = device_id
        additions_client.append(
            "\n".join(
                [
                    f"config rtu_server {_q(device_id)}",
                    f"\toption server_id {_q(device.slave_id)}",
                    f"\toption rtu_device {_q(connection_ids[device.connection])}",
                    "\toption skip_on_many_tmos '0'",
                    f"\toption timeout {_q(device.timeout)}",
                    f"\toption period {_q(device.period)}",
                    "\toption frequency 'period'",
                    f"\toption name {_q(device.name)}",
                    f"\toption enabled {_q(_on(device.enabled))}",
                ]
            )
        )

        for request in device.requests:
            request_id = next_id
            next_id += 1
            request_ids[(device.name, request.name)] = request_id
            additions_client.append(
                "\n".join(
                    [
                        f"config request_{device_id} {_q(request_id)}",
                        f"\toption name {_q(request.name)}",
                        f"\toption enabled {_q(_on(request.enabled))}",
                        f"\toption function {_q(int(request.function))}",
                        f"\toption data_type {_q(_request_data_type(request))}",
                        f"\toption reg_count {_q(request.count)}",
                        "\toption store_on_change_only '0'",
                        f"\toption first_reg {_q(request.register)}",
                        "\toption no_brackets '0'",
                        "\toption broadcast '0'",
                    ]
                )
            )

    next_tag_id = _numeric_max([s for s in server_sections if s.section_type == "tag"]) + 1
    additions_server: list[str] = []
    for mapping in new_mappings:
        if mapping.device not in device_ids:
            raise ValueError(f"Mapping {mapping.name!r} references unknown device {mapping.device!r}")
        source_key = (mapping.device, mapping.request)
        if source_key not in request_ids:
            raise ValueError(
                f"Mapping {mapping.name!r} references request {mapping.device}/{mapping.request}, "
                "but no imported/new request UCI ID is available."
            )
        try:
            modbus_type = REGISTER_TYPES[mapping.register_type]
        except KeyError as exc:
            raise ValueError(
                f"Unsupported mapping register_type: {mapping.register_type}"
            ) from exc

        source_device_id = device_ids[mapping.device]
        source_request_id = request_ids[source_key]
        tag_section_id = next_tag_id
        next_tag_id += 1
        additions_server.append(
            "\n".join(
                [
                    f"config tag {_q(tag_section_id)}",
                    "\toption modbus_dev_config 'modbus'",
                    f"\toption tag_name {_q(mapping.name)}",
                    "\toption tag_source 'modbus_client'",
                    "\toption tag_permissions 'r'",
                    "\toption tag_start '0'",
                    f"\toption modbus_reg_num {_q(mapping.register)}",
                    f"\toption modbus_type {_q(modbus_type)}",
                    f"\toption tag_id {_q(f'{source_device_id}.{source_request_id}')}",
                    f"\toption enabled {_q(_on(mapping.enabled))}",
                    "\toption tag_type 'int16'",
                    "\toption tag_count '1'",
                ]
            )
        )

    return GeneratedUci(
        modbus_client=_append_sections(source.modbus_client, additions_client),
        modbus_server=_append_sections(source.modbus_server, additions_server),
    )


def _generate_fresh(project: Project) -> GeneratedUci:
    client: list[str] = [
        "package modbus_client",
        "",
        "config main 'main'",
        "\toption debug '0'",
        "\toption enabled '1'",
        "",
    ]

    next_id = 1
    connection_ids: dict[str, int] = {}
    device_ids: dict[str, int] = {}
    request_ids: dict[tuple[str, str], int] = {}

    for connection in project.connections:
        connection_id = next_id
        next_id += 1
        connection_ids[connection.name] = connection_id
        client.extend(
            [
                f"config rtu_device {_q(connection_id)}",
                "\toption full_duplex_enabled '0'",
                f"\toption device {_q(connection.device)}",
                f"\toption baudrate {_q(connection.baudrate)}",
                "\toption flowcontrol 'none'",
                f"\toption databits {_q(connection.databits)}",
                f"\toption parity {_q(connection.parity)}",
                f"\toption name {_q(connection.name)}",
                f"\toption stopbits {_q(connection.stopbits)}",
                "\toption enabled '1'",
                "",
            ]
        )

    for device in project.devices:
        device_id = next_id
        next_id += 1
        device_ids[device.name] = device_id

        client.extend(
            [
                f"config rtu_server {_q(device_id)}",
                f"\toption server_id {_q(device.slave_id)}",
                f"\toption rtu_device {_q(connection_ids[device.connection])}",
                "\toption skip_on_many_tmos '0'",
                f"\toption timeout {_q(device.timeout)}",
                f"\toption period {_q(device.period)}",
                "\toption frequency 'period'",
                f"\toption name {_q(device.name)}",
                f"\toption enabled {_q(_on(device.enabled))}",
                "",
            ]
        )

        for request in device.requests:
            request_id = next_id
            next_id += 1
            request_ids[(device.name, request.name)] = request_id
            client.extend(
                [
                    f"config request_{device_id} {_q(request_id)}",
                    f"\toption name {_q(request.name)}",
                    f"\toption enabled {_q(_on(request.enabled))}",
                    f"\toption function {_q(int(request.function))}",
                    f"\toption data_type {_q(_request_data_type(request))}",
                    f"\toption reg_count {_q(request.count)}",
                    "\toption store_on_change_only '0'",
                    f"\toption first_reg {_q(request.register)}",
                    "\toption no_brackets '0'",
                    "\toption broadcast '0'",
                    "",
                ]
            )

    tcp = project.tcp_server
    server: list[str] = [
        "package modbus_server",
        "",
        "config modbus 'modbus'",
        f"\toption keepconn {_q(_on(tcp.keep_connection))}",
        "\toption timeout '0'",
        f"\toption port {_q(tcp.port)}",
        "\toption md_data_type '0'",
        "\toption clientregs '0'",
        "\toption broadcasts '0'",
        f"\toption device_id {_q(tcp.device_id)}",
        f"\toption enabled {_q(_on(tcp.enabled))}",
        "",
    ]

    for tag_section_id, mapping in enumerate(project.mappings, start=1):
        try:
            modbus_type = REGISTER_TYPES[mapping.register_type]
        except KeyError as exc:
            raise ValueError(
                f"Unsupported mapping register_type: {mapping.register_type}"
            ) from exc

        source_device_id = device_ids[mapping.device]
        source_request_id = request_ids[(mapping.device, mapping.request)]

        server.extend(
            [
                f"config tag {_q(tag_section_id)}",
                "\toption modbus_dev_config 'modbus'",
                f"\toption tag_name {_q(mapping.name)}",
                "\toption tag_source 'modbus_client'",
                "\toption tag_permissions 'r'",
                "\toption tag_start '0'",
                f"\toption modbus_reg_num {_q(mapping.register)}",
                f"\toption modbus_type {_q(modbus_type)}",
                f"\toption tag_id {_q(f'{source_device_id}.{source_request_id}')}",
                f"\toption enabled {_q(_on(mapping.enabled))}",
                "\toption tag_type 'int16'",
                "\toption tag_count '1'",
                "",
            ]
        )

    return GeneratedUci(
        modbus_client="\n".join(client).rstrip() + "\n",
        modbus_server="\n".join(server).rstrip() + "\n",
    )


def generate_uci(project: Project) -> GeneratedUci:
    messages = validate_project(project)
    raise_for_errors(messages)
    if project.source_uci is not None:
        return _generate_from_imported(project)
    return _generate_fresh(project)
