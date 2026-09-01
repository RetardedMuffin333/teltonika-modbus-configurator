from teltonika_modbus_configurator.live_test import LiveTestTarget
from teltonika_modbus_configurator.models import FunctionCode, Request
from teltonika_modbus_configurator.rutos_api import RutOSApiClient


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
