from teltonika_modbus_configurator.live_test import (
    device_templates,
    make_adhoc_target,
    make_adhoc_write_target,
    project_test_targets,
    read_targets_for_device,
    run_timed_test,
    write_targets,
)
from teltonika_modbus_configurator.models import Device, FunctionCode, Request, SerialConnection, TcpClientDevice


def test_project_targets_include_rtu_and_tcp_request_details():
    rtu = Device(
        name="Thermostat",
        slave_id=7,
        connection="RS485",
        requests=[Request("RoomTemp", FunctionCode.READ_INPUT_REGISTERS, 5, count=1)],
    )
    tcp = TcpClientDevice(
        name="Carel",
        server_id=1,
        host="192.168.2.20",
        port=502,
        requests=[Request("ZunTemp", FunctionCode.READ_HOLDING_REGISTERS, 241, count=2, data_type="float32", byte_order="1234")],
    )
    serial = SerialConnection("RS485", baudrate=19200, databits=8, parity="none", stopbits=1)

    targets = project_test_targets([rtu], [tcp], [serial])

    assert [target.summary for target in targets] == [
        "RTU | Thermostat | RoomTemp",
        "TCP | Carel | ZunTemp",
    ]
    assert targets[0].device_id == 7
    assert targets[0].baudrate == 19200
    assert targets[0].serial_type == "/dev/rs485"
    assert targets[1].device_id == 1
    assert targets[1].host == "192.168.2.20"
    assert targets[1].port == 502
    assert targets[1].request.register == 241
    assert targets[1].request.count == 2


def test_device_templates_return_one_entry_per_device():
    device = Device(
        name="Thermostat",
        slave_id=7,
        connection="RS485",
        requests=[
            Request("A", FunctionCode.READ_INPUT_REGISTERS, 1),
            Request("B", FunctionCode.READ_INPUT_REGISTERS, 2),
        ],
    )
    tcp = TcpClientDevice(
        name="Carel",
        requests=[Request("C", FunctionCode.READ_HOLDING_REGISTERS, 3)],
    )
    targets = project_test_targets([device], [tcp])
    assert [target.device_summary for target in device_templates(targets)] == [
        "RTU | Thermostat",
        "TCP | Carel",
    ]


def test_device_scan_selects_only_enabled_read_requests_for_device():
    device = Device(
        name="Thermostat",
        slave_id=7,
        connection="RS485",
        requests=[
            Request("ReadA", FunctionCode.READ_INPUT_REGISTERS, 1),
            Request("DisabledRead", FunctionCode.READ_INPUT_REGISTERS, 2, enabled=False),
            Request("WriteA", FunctionCode.WRITE_SINGLE_HOLDING_REGISTER, 3, values="1"),
        ],
    )
    other = Device(
        name="Other",
        slave_id=8,
        connection="RS485",
        requests=[Request("OtherRead", FunctionCode.READ_INPUT_REGISTERS, 4)],
    )
    targets = project_test_targets([device, other], [])
    template = device_templates(targets)[0]
    assert [target.request.name for target in read_targets_for_device(targets, template)] == ["ReadA"]


def test_make_adhoc_target_inherits_transport_and_replaces_request():
    tcp = TcpClientDevice(
        name="Carel",
        server_id=2,
        host="192.168.2.20",
        source_id="123",
        requests=[Request("Existing", FunctionCode.READ_HOLDING_REGISTERS, 9)],
    )
    template = project_test_targets([], [tcp])[0]
    target = make_adhoc_target(
        template,
        function=3,
        register=241,
        count=1,
        data_type="float32",
        byte_order="1234",
    )
    assert target.device_name == "Carel"
    assert target.device_id == 2
    assert target.host == "192.168.2.20"
    assert target.config_id == "123"
    assert target.request.name == "Ad-hoc"
    assert target.request.register == 241
    assert target.request.data_type == "float32"
    assert target.request.byte_order == "1234"


def test_make_adhoc_coil_read_forces_bool_format():
    tcp = TcpClientDevice(name="Carel", requests=[Request("Existing", FunctionCode.READ_COILS, 1)])
    template = project_test_targets([], [tcp])[0]
    target = make_adhoc_target(
        template,
        function=1,
        register=112,
        count=1,
        data_type="float32",
        byte_order="1234",
    )
    assert target.request.data_type == "bool"
    assert target.request.byte_order == "none"


def test_write_targets_include_disabled_scada_commands():
    tcp = TcpClientDevice(name="Carel", requests=[
        Request("Read", FunctionCode.READ_HOLDING_REGISTERS, 1),
        Request("Write", FunctionCode.WRITE_SINGLE_HOLDING_REGISTER, 1, enabled=False, values="9"),
    ])
    targets = project_test_targets([], [tcp])
    assert [target.request.name for target in write_targets(targets)] == ["Write"]


def test_make_adhoc_float_write_uses_fc16_and_value():
    tcp = TcpClientDevice(name="Carel", requests=[Request("Read", FunctionCode.READ_HOLDING_REGISTERS, 1)])
    template = project_test_targets([], [tcp])[0]
    target = make_adhoc_write_target(
        template, function=16, register=7, values="21.5",
        data_type="float32", byte_order="1234",
    )
    assert target.request.function == FunctionCode.WRITE_MULTIPLE_HOLDING_REGISTERS
    assert target.request.values == "21.5"
    assert target.request.enabled is False


def test_make_adhoc_coil_write_normalizes_boolean_values():
    tcp = TcpClientDevice(name="Carel", requests=[Request("Read", FunctionCode.READ_COILS, 1)])
    template = project_test_targets([], [tcp])[0]
    target = make_adhoc_write_target(
        template, function=15, register=7, values="true 0 false 1",
        data_type="float32", byte_order="1234",
    )
    assert target.request.values == "1 0 0 1"
    assert target.request.data_type == "bool"
    assert target.request.byte_order == "none"


def test_make_adhoc_write_rejects_32bit_fc06():
    tcp = TcpClientDevice(name="Carel", requests=[Request("Read", FunctionCode.READ_HOLDING_REGISTERS, 1)])
    template = project_test_targets([], [tcp])[0]
    try:
        make_adhoc_write_target(
            template, function=6, register=7, values="21.5",
            data_type="float32", byte_order="1234",
        )
    except ValueError as exc:
        assert "use FC16" in str(exc)
    else:
        raise AssertionError("Expected FC06 FLOAT32 to be rejected")


def test_timed_test_captures_success_and_raw_response():
    result = run_timed_test(lambda: ("8.5625", "[8.5625]"))
    assert result.ok is True
    assert result.value == "8.5625"
    assert result.raw_response == "[8.5625]"
    assert result.elapsed_ms >= 0


def test_timed_test_captures_transport_error():
    def fail():
        raise RuntimeError("Modbus timeout")

    result = run_timed_test(fail)
    assert result.ok is False
    assert result.value == ""
    assert result.error == "Modbus timeout"
