from teltonika_modbus_configurator.models import Device, FunctionCode, Project, Request, TcpClientDevice
from teltonika_modbus_configurator.request_mapping import create_tcp_mappings_from_requests


def test_create_tcp_mappings_from_rtu_requests_packs_each_address_space() -> None:
    device = Device(
        name="RDF",
        slave_id=1,
        connection="RS485",
        requests=[
            Request("Mode", FunctionCode.READ_INPUT_REGISTERS, 4, data_type="int16"),
            Request("Temp", FunctionCode.READ_INPUT_REGISTERS, 5, data_type="float32"),
            Request("Run", FunctionCode.READ_COILS, 10, data_type="bool"),
        ],
    )
    project = Project(devices=[device])

    result = create_tcp_mappings_from_requests(
        project,
        device_name="RDF",
        request_names=["Mode", "Temp", "Run"],
    )

    assert len(result.created) == 3
    assert result.skipped == []
    by_name = {mapping.request: mapping for mapping in result.created}
    assert (by_name["Mode"].register_type, by_name["Mode"].register) == ("input_register", 1025)
    assert (by_name["Temp"].register_type, by_name["Temp"].register) == ("input_register", 1026)
    assert by_name["Temp"].data_type == "float32"
    assert (by_name["Run"].register_type, by_name["Run"].register) == ("coil", 1025)


def test_float32_mapping_reserves_two_server_registers() -> None:
    device = TcpClientDevice(
        name="Carel",
        host="192.168.2.20",
        requests=[
            Request("A", FunctionCode.READ_HOLDING_REGISTERS, 10, data_type="float32"),
            Request("B", FunctionCode.READ_HOLDING_REGISTERS, 11, data_type="int16"),
        ],
    )
    project = Project(tcp_clients=[device])

    result = create_tcp_mappings_from_requests(project, device_name="Carel", request_names=["A", "B"])

    assert [mapping.register for mapping in result.created] == [1025, 1027]
    assert all(mapping.register_type == "holding_register" for mapping in result.created)


def test_repeat_action_skips_existing_device_request_mapping() -> None:
    device = Device(
        name="RDF",
        slave_id=1,
        connection="RS485",
        requests=[Request("Mode", FunctionCode.READ_INPUT_REGISTERS, 4)],
    )
    project = Project(devices=[device])

    first = create_tcp_mappings_from_requests(project, device_name="RDF", request_names=["Mode"])
    second = create_tcp_mappings_from_requests(project, device_name="RDF", request_names=["Mode"])

    assert len(first.created) == 1
    assert second.created == []
    assert second.skipped == ["Mode: TCP Server mapping already exists"]
    assert len(project.mappings) == 1


def test_write_request_creates_write_only_holding_mapping() -> None:
    device = TcpClientDevice(
        name="Carel",
        requests=[
            Request(
                "Setpoint_Write",
                FunctionCode.WRITE_SINGLE_HOLDING_REGISTER,
                20,
                data_type="uint16",
                values="25",
                enabled=False,
            )
        ],
    )
    project = Project(tcp_clients=[device])

    result = create_tcp_mappings_from_requests(project, device_name="Carel", request_names=["Setpoint_Write"])

    mapping = result.created[0]
    assert mapping.register_type == "holding_register"
    assert mapping.permissions == "w"
    assert mapping.data_type == "uint16"
    assert mapping.register == 1025
