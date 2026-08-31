from teltonika_modbus_configurator.carel_convert import (
    apply_carel_import_plan,
    build_carel_import_plan,
    repack_carel_import_items,
)
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


def test_selected_sparse_coils_are_repacked_without_preview_gaps():
    project = _project()
    rows = [
        CarelImportRow("Documentation", 2, "Coil_A", "110", "Coil", "1", "Bool", "Read"),
        CarelImportRow("Documentation", 3, "Coil_B", "111", "Coil", "1", "Bool", "Read"),
        CarelImportRow("Documentation", 4, "Coil_C", "150", "Coil", "1", "Bool", "Read"),
        CarelImportRow("Documentation", 5, "Coil_D", "151", "Coil", "1", "Bool", "Read"),
        CarelImportRow("Documentation", 6, "Coil_E", "159", "Coil", "1", "Bool", "Read"),
    ]
    plan = build_carel_import_plan(project, rows, tcp_device_name="Carel", mapping_start=1025)
    # Simulate selecting non-adjacent rows from the full preview plan.
    selected = [plan[0], plan[2], plan[3], plan[4]]
    packed = repack_carel_import_items(project, selected, mapping_start=1025)

    assert [item.mapping.register for item in packed] == [1025, 1026, 1027, 1028]
    assert [item.request.register for item in packed] == [111, 151, 152, 160]


def test_selected_mixed_areas_pack_independently_and_preserve_32bit_width():
    project = _project()
    rows = [
        CarelImportRow("Documentation", 2, "Coil_A", "1", "Coil", "1", "Bool", "Read"),
        CarelImportRow("Documentation", 3, "Float_A", "10", "HoldingRegister", "2", "Real", "Read"),
        CarelImportRow("Documentation", 4, "Float_B", "12", "HoldingRegister", "2", "Real", "Read"),
        CarelImportRow("Documentation", 5, "Coil_B", "2", "Coil", "1", "Bool", "Read"),
    ]
    plan = build_carel_import_plan(project, rows, tcp_device_name="Carel", mapping_start=1200)
    packed = repack_carel_import_items(project, [plan[0], plan[1], plan[2], plan[3]], mapping_start=1200)

    assert [item.mapping.register for item in packed if item.mapping.register_type == "coil"] == [1200, 1201]
    assert [item.mapping.register for item in packed if item.mapping.register_type == "holding_register"] == [1200, 1202]


def test_unsupported_datatype_is_skipped_not_guessed():
    project = _project()
    rows = [CarelImportRow("Documentation", 2, "X", "10", "HoldingRegister", "4", "LReal", "Read")]
    plan = build_carel_import_plan(project, rows, tcp_device_name="Carel")
    assert plan[0].request is None
    assert "unsupported Carel datatype" in plan[0].status
