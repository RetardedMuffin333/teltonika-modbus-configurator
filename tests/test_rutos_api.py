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


def test_display_value_normalizes_rut956_bracketed_result():
    assert _display_value("[8.312500]") == "8.312500"
