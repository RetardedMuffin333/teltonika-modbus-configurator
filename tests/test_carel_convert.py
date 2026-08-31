from teltonika_modbus_configurator.carel_convert import apply_carel_import_plan, build_carel_import_plan
from teltonika_modbus_configurator.carel_import import CarelImportRow
from teltonika_modbus_configurator.models import Project, TcpClientDevice


def _project():
    return Project(tcp_clients=[TcpClientDevice(name="Carel", host="192.168.2.20", port=502, server_id=1)])


def test_carel_plan_maps_area_datatype_and_plus_one_address():
    project = _project()
    rows = [
        CarelImportRow("Documentation", 2, "AI_U5_ZunTemp", "240", "HoldingRegister", "2", "Real", "ReadWrite"),
        CarelImportRow("Documentation", 3, "Alarm", "5", "DiscreteInput", "1", "Bool", "Read"),
    ]
    plan = build_carel_import_plan(project, rows, tcp_device_name="Carel", add_one_to_index=True, mapping_start=1100)

    first = plan[0]
    assert int(first.request.function) == 3
    assert first.request.register == 241
    assert first.request.data_type == "float32"
    assert first.request.byte_order == "1234"
    assert first.mapping.register_type == "holding_register"
    assert first.mapping.register == 1100

    second = plan[1]
    assert int(second.request.function) == 2
    assert second.request.register == 6
    assert second.request.data_type == "bool"
    assert second.mapping.register_type == "discrete_input"
    assert second.mapping.register == 1100


def test_carel_plan_reserves_two_server_registers_for_32bit_values():
    project = _project()
    rows = [
        CarelImportRow("Documentation", 2, "A", "1", "HoldingRegister", "2", "DInt", "Read"),
        CarelImportRow("Documentation", 3, "B", "3", "HoldingRegister", "1", "UInt", "Read"),
    ]
    plan = build_carel_import_plan(project, rows, tcp_device_name="Carel", mapping_start=1300)
    assert plan[0].mapping.register == 1300
    assert plan[1].mapping.register == 1302


def test_readwrite_creates_read_path_only_and_apply_adds_ready_rows():
    project = _project()
    rows = [CarelImportRow("Documentation", 2, "Setpoint", "10", "HoldingRegister", "1", "UInt", "ReadWrite")]
    plan = build_carel_import_plan(project, rows, tcp_device_name="Carel")
    assert int(plan[0].request.function) == 3
    assert plan[0].request.enabled is True
    assert plan[0].mapping.permissions == "r"

    count = apply_carel_import_plan(project, plan, tcp_device_name="Carel")
    assert count == 1
    assert project.tcp_clients[0].requests[0].name == "Setpoint"
    assert project.mappings[0].name == "Setpoint"


def test_unsupported_datatype_is_skipped_not_guessed():
    project = _project()
    rows = [CarelImportRow("Documentation", 2, "X", "10", "HoldingRegister", "4", "LReal", "Read")]
    plan = build_carel_import_plan(project, rows, tcp_device_name="Carel")
    assert plan[0].request is None
    assert "unsupported Carel datatype" in plan[0].status
