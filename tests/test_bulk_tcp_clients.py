from teltonika_modbus_configurator.bulk import BulkMappingSpec, BulkRequestSpec, BulkSpec, generate_bulk
from teltonika_modbus_configurator.models import FunctionCode, Project, SerialConnection, TcpClientDevice


def test_bulk_generates_tcp_clients_not_rtu_devices():
    project = Project(connections=[SerialConnection("RS485")])
    spec = BulkSpec(
        transport="tcp",
        connection="",
        host="10.33.24.5",
        port=502,
        name_pattern="TCP_Test{index}",
        count=2,
        slave_start=3,
        period=10,
        timeout=1,
        enabled=False,
        requests=[BulkRequestSpec("IR", FunctionCode.READ_INPUT_REGISTERS, 12)],
        mappings=[BulkMappingSpec("{device}_IR", "IR", "input_register", 1200, enabled=False)],
    )
    result = generate_bulk(project, spec)
    assert result.devices == []
    assert [d.name for d in result.tcp_clients] == ["TCP_Test1", "TCP_Test2"]
    assert [d.server_id for d in result.tcp_clients] == [3, 4]
    assert all(d.host == "10.33.24.5" and d.port == 502 for d in result.tcp_clients)
    assert [m.device for m in result.mappings] == ["TCP_Test1", "TCP_Test2"]


def test_tcp_bulk_rejects_existing_host_port_unit_tuple():
    project = Project(tcp_clients=[TcpClientDevice("Existing", server_id=2, host="10.33.24.5", port=502)])
    spec = BulkSpec(
        transport="tcp", connection="", host="10.33.24.5", port=502,
        name_pattern="New{index}", count=1, slave_start=2,
    )
    from teltonika_modbus_configurator.bulk import validate_bulk_spec
    errors = validate_bulk_spec(project, spec)
    assert any("Unit ID 2 is already used" in e for e in errors)


def test_rtu_bulk_backwards_compatibility_still_works():
    project = Project(connections=[SerialConnection("RS485")])
    spec = BulkSpec(connection="RS485", name_pattern="Room{index}", count=1, slave_start=7)
    result = generate_bulk(project, spec)
    assert len(result.devices) == 1
    assert result.devices[0].slave_id == 7
    assert result.tcp_clients == []
