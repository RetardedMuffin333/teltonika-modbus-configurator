from teltonika_modbus_configurator.models import Device, Project, SerialConnection, TcpClientDevice
from teltonika_modbus_configurator.symbol_import import (
    apply_symbol_import_plan,
    build_symbol_import_plan,
    load_symbol_file,
)
from teltonika_modbus_configurator.atvise_symbols import export_atvise_symbols
from teltonika_modbus_configurator.uci_generator import generate_uci


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


def test_symbol_plan_maps_known_types_including_verified_hrd_dint():
    project = Project(tcp_clients=[TcpClientDevice(name="PLC", host="10.0.0.2")])
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

    hrd = plan[2]
    assert hrd.request is not None
    assert hrd.mapping is not None
    assert hrd.request.register == 84
    assert hrd.request.data_type == "int32"
    assert hrd.request.byte_order == "1234"
    assert hrd.request.count == 2
    assert hrd.mapping.register_type == "holding_register"
    assert hrd.mapping.data_type == "int32"
    assert hrd.mapping.count == 1
    # HR at 1025 consumes one register, HRD then consumes 1026-1027.
    assert hrd.mapping.register == 1026


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


def test_selected_hrd_rows_are_repacked_as_two_register_values():
    project = Project(tcp_clients=[TcpClientDevice(name="PLC", host="10.0.0.2")])
    from teltonika_modbus_configurator.symbol_import import SymbolRow
    rows = [
        SymbolRow(1, "Day", "HRD", 47),
        SymbolRow(2, "CopyToDay", "HRD", 50),
    ]
    plan = build_symbol_import_plan(project, rows, device_name="PLC", mapping_start=1200)
    assert [item.request.count for item in plan] == [2, 2]
    assert [item.mapping.register for item in plan] == [1200, 1202]


def test_symbol_import_can_use_same_physical_batch_model_as_register_tables():
    project = Project(tcp_clients=[TcpClientDevice(name="PLC", host="10.0.0.2")])
    from teltonika_modbus_configurator.symbol_import import SymbolRow
    rows = [
        SymbolRow(1, "Temperature", "HRR", 10),
        SymbolRow(2, "Mode", "HR", 12),
        SymbolRow(3, "Scheduler_Day", "HRD", 20),
    ]
    plan = build_symbol_import_plan(project, rows, device_name="PLC", mapping_start=1025)

    assert apply_symbol_import_plan(
        project, plan, device_name="PLC", mapping_start=1025, batch_reads=True
    ) == 3

    assert [(r.name, r.register, r.count, r.data_type) for r in project.tcp_clients[0].requests] == [
        ("Batch_FC03_10_21", 10, 12, "uint16")
    ]
    deployed = [m for m in project.mappings if m.deploy]
    aliases = {m.name: m for m in project.mappings if not m.deploy}
    assert [(m.name, m.register, m.count, m.export_symbol) for m in deployed] == [
        ("Batch_FC03_10_21", 1025, 12, False)
    ]
    assert (aliases["Temperature"].register, aliases["Temperature"].source_offset) == (1025, 0)
    assert (aliases["Mode"].register, aliases["Mode"].source_offset) == (1027, 2)
    assert (aliases["Scheduler_Day"].register, aliases["Scheduler_Day"].source_offset) == (1035, 10)

    generated = generate_uci(project)
    assert generated.modbus_client.count("config request_") == 1
    assert generated.modbus_server.count("config tag ") == 1
    symbols = export_atvise_symbols(project)
    assert "sym-Temperature=HRR1025," in symbols
    assert "sym-Mode=HR1027," in symbols
    assert "sym-Scheduler_Day=HRD1035," in symbols
