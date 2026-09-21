from teltonika_modbus_configurator.live_test import LiveTestTarget
from teltonika_modbus_configurator.models import FunctionCode, Request
from teltonika_modbus_configurator.rutos_api import RutOSApiClient, _display_value


def test_tcp_test_payload_preserves_modbus_request(monkeypatch):
    target = LiveTestTarget(
        transport="tcp",
        device_name="Carel",
        device_id=2,
        request=Request("Temp", FunctionCode.READ_HOLDING_REGISTERS, 241, count=2, data_type="float32", byte_order="1234"),
        host="192.168.2.20",
        port=502,
        timeout=5,
        config_id="123",
    )
    client = RutOSApiClient("192.168.2.1", "admin", "secret")
    captured = {}

    def fake_post(endpoint, data):
        captured["endpoint"] = endpoint
        captured["data"] = data
        return {"success": True, "data": {"value": "8.5625"}}

    monkeypatch.setattr(client, "post", fake_post)
    result = client.test_tcp(target)

    assert captured["endpoint"] == "modbus/client/tcp/123/requests/actions/test_request"
    assert captured["data"] == {
        "server_id": "2",
        "timeout": "5",
        "function": "3",
        "first_reg": "241",
        "reg_count": "2",
        "data_type": "32bit_float1234",
        "no_brackets": "0",
        "dev_ipaddr": "192.168.2.20",
        "port": "502",
        "delay": "0",
    }
    assert result["success"] is True


def test_serial_test_payload_uses_rutos_server_id(monkeypatch):
    target = LiveTestTarget(
        transport="rtu",
        device_name="RDF400MB",
        device_id=7,
        request=Request("RoomTemp", FunctionCode.READ_INPUT_REGISTERS, 5, count=1),
        timeout=1,
        config_id="42",
        serial_type="/dev/rs485",
        baudrate=19200,
        databits=8,
        parity="none",
        stopbits=1,
        flowcontrol="none",
    )
    client = RutOSApiClient("192.168.2.1", "admin", "secret")
    captured = {}

    def fake_post(endpoint, data):
        captured["endpoint"] = endpoint
        captured["data"] = data
        return {"success": True, "data": {"result": "[21.50]", "error": 0}}

    monkeypatch.setattr(client, "post", fake_post)
    result = client.test_serial(target)

    assert captured["endpoint"] == "modbus/client/serial/servers/42/requests/actions/test_request"
    assert captured["data"] == {
        "server_id": "7",
        "timeout": "1",
        "function": "4",
        "first_reg": "5",
        "reg_count": "1",
        "data_type": "16bit_int_hi_first",
        "no_brackets": "0",
        "type": "/dev/rs485",
        "flowcontrol": "none",
        "parity": "none",
        "databits": "8",
        "stopbits": "1",
        "baudrate": "19200",
        "broadcast": "0",
    }
    assert result["success"] is True


def test_serial_test_requires_imported_server_configuration_id():
    target = LiveTestTarget(
        transport="rtu",
        device_name="RDF400MB",
        device_id=7,
        request=Request("RoomTemp", FunctionCode.READ_INPUT_REGISTERS, 5),
    )
    client = RutOSApiClient("192.168.2.1", "admin", "secret")

    try:
        client.test_serial(target)
    except RuntimeError as exc:
        assert "Import the live gateway configuration first" in str(exc)
    else:
        raise AssertionError("Expected missing RTU config ID to be rejected")


def test_write_payload_places_values_in_rutos_reg_count(monkeypatch):
    target = LiveTestTarget(
        transport="tcp", device_name="Carel", device_id=1,
        request=Request("Setpoint", FunctionCode.WRITE_MULTIPLE_HOLDING_REGISTERS, 7, data_type="float32", byte_order="1234", enabled=False, values="21.5"),
        host="192.168.2.20", port=502, timeout=1, config_id="9",
    )
    client = RutOSApiClient("192.168.2.1", "admin", "secret")
    captured = {}
    monkeypatch.setattr(client, "post", lambda endpoint, data: captured.update(endpoint=endpoint, data=data) or {"success": True})

    client.test_tcp(target)

    assert captured["data"]["function"] == "16"
    assert captured["data"]["reg_count"] == "21.5"
    assert captured["data"]["data_type"] == "32bit_float1234"


def test_display_value_normalizes_rut956_bracketed_result():
    assert _display_value("[8.312500]") == "8.312500"
