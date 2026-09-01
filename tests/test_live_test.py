from teltonika_modbus_configurator.live_test import project_test_targets, run_timed_test
from teltonika_modbus_configurator.models import Device, FunctionCode, Request, TcpClientDevice


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

    targets = project_test_targets([rtu], [tcp])

    assert [target.summary for target in targets] == [
        "RTU | Thermostat | RoomTemp",
        "TCP | Carel | ZunTemp",
    ]
    assert targets[0].device_id == 7
    assert targets[1].device_id == 1
    assert targets[1].host == "192.168.2.20"
    assert targets[1].port == 502
    assert targets[1].request.register == 241
    assert targets[1].request.count == 2


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
