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


def generate_uci(project: Project) -> GeneratedUci:
    messages = validate_project(project)
    raise_for_errors(messages)

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
