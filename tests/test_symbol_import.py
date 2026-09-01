from teltonika_modbus_configurator.models import Device, Project, SerialConnection, TcpClientDevice
from teltonika_modbus_configurator.symbol_import import (
    apply_symbol_import_plan,
    build_symbol_import_plan,
    load_symbol_file,
)


def test_load_symbol_file_parses_real_syntax(tmp_path):
    path = tmp_path / "Conn.Symbol"
    path.write_text(
        "[]\n"
        "sym-Temperature=IRR97,\n"
        "sym-Mode=HR3,\n"
        "sym-Alarm=DI51,\n"
        "sym-Enable=DA12,\n"
        "sym-Scheduler_Day=HRD84,\n",
        encoding="utf-8",
    )
    preview = load_symbol_file(path)
    assert [(r.name, r.symbol_type, r.register) for r in preview.rows] == [
        ("Temperature", "IRR", 97),
        ("Mode", "HR", 3),
        ("Alarm", "DI", 51),
        ("Enable", "DA", 12),
        ("Scheduler_Day", "HRD", 84),
    ]
    assert preview.ignored_lines == 0


def test_symbol_plan_maps_known_types_and_leaves_hrd_unsupported():
    project = Project(tcp_clients=[TcpClientDevice(name="PLC", host="10.0.0.2")])
    rows = load_symbol_file_from_text = None
    from teltonika_modbus_configurator.symbol_import import SymbolRow
    rows = [
        SymbolRow(1, "Temperature", "IRR", 97),
        SymbolRow(2, "Mode", "HR", 3),
        SymbolRow(3, "Scheduler_Day", "HRD", 84),
    ]
    plan = build_symbol_import_plan(project, rows, device_name="PLC", mapping_start=1025)
    assert plan[0].request.register == 97
    assert plan[0].request.data_type == "float32"
    assert plan[0].mapping.register_type == "input_register"
    assert plan[0].mapping.register == 1025
    assert plan[1].request.data_type == "int16"
    assert plan[1].mapping.register_type == "holding_register"
    assert plan[1].mapping.register == 1025
    assert plan[2].request is None
    assert "HRD" in plan[2].status


def test_symbol_import_supports_rtu_target_and_offset():
    project = Project(
        connections=[SerialConnection(name="RS485")],
        devices=[Device(name="Thermostat", slave_id=1, connection="RS485")],
    )
    from teltonika_modbus_configurator.symbol_import import SymbolRow
    rows = [SymbolRow(1, "RoomTemp", "IR", 4)]
    plan = build_symbol_import_plan(project, rows, device_name="Thermostat", source_address_offset=1)
    assert plan[0].request.register == 5
    assert apply_symbol_import_plan(project, plan, device_name="Thermostat") == 1
    assert project.devices[0].requests[0].name == "RoomTemp"
    assert project.mappings[0].device == "Thermostat"


def test_selected_float_rows_are_repacked_without_gaps():
    project = Project(tcp_clients=[TcpClientDevice(name="PLC", host="10.0.0.2")])
    from teltonika_modbus_configurator.symbol_import import SymbolRow
    rows = [
        SymbolRow(1, "A", "HRR", 10),
        SymbolRow(2, "B", "HRR", 20),
        SymbolRow(3, "C", "HRR", 30),
    ]
    plan = build_symbol_import_plan(project, rows, device_name="PLC", mapping_start=1100)
    assert apply_symbol_import_plan(project, [plan[0], plan[2]], device_name="PLC", mapping_start=1100) == 2
    assert [m.register for m in project.mappings] == [1100, 1102]
