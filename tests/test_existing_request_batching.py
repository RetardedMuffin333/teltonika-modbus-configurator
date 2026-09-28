from teltonika_modbus_configurator.atvise_symbols import export_atvise_symbols
from teltonika_modbus_configurator.existing_request_batching import (
    apply_existing_batch_plan,
    build_existing_batch_plan,
)
from teltonika_modbus_configurator.models import (
    FunctionCode,
    Project,
    Request,
    ServerMapping,
    TcpClientDevice,
)
from teltonika_modbus_configurator.uci_generator import generate_uci


def _project() -> Project:
    requests = [
        Request("OutsideTemp", FunctionCode.READ_HOLDING_REGISTERS, 10, count=2, data_type="float32", byte_order="1234"),
        Request("Setpoint", FunctionCode.READ_HOLDING_REGISTERS, 12, data_type="int16"),
        Request("Alarm", FunctionCode.READ_COILS, 20, data_type="bool", byte_order="none"),
        Request("WriteSetpoint", FunctionCode.WRITE_SINGLE_HOLDING_REGISTER, 12, values="20", data_type="int16"),
    ]
    mappings = [
        ServerMapping("OutsideTemp", "PLC", "OutsideTemp", 1025, "holding_register", data_type="float32"),
        ServerMapping("Setpoint", "PLC", "Setpoint", 1027, "holding_register", data_type="int16"),
        ServerMapping("Alarm", "PLC", "Alarm", 1025, "coil", data_type="bool"),
        ServerMapping("WriteSetpoint", "PLC", "WriteSetpoint", 20000, "holding_register", permissions="w", data_type="int16"),
    ]
    return Project(tcp_clients=[TcpClientDevice("PLC", requests=requests)], mappings=mappings)


def test_selected_individual_reads_become_batches_and_keep_symbol_names():
    project = _project()
    plan = build_existing_batch_plan(
        project, device_name="PLC", request_names=["OutsideTemp", "Setpoint", "Alarm"]
    )

    assert plan.ready_count == 3
    assert [(request.name, request.register, request.count) for request in plan.batch_requests] == [
        ("Batch_FC03_10_12", 10, 3),
        ("Batch_FC01_20_20", 20, 1),
    ]
    assert apply_existing_batch_plan(project, plan) == 3

    source = project.tcp_clients[0]
    assert {request.name for request in source.requests} == {
        "WriteSetpoint", "Batch_FC03_10_12", "Batch_FC01_20_20"
    }
    deployed = [mapping for mapping in project.mappings if mapping.deploy]
    aliases = {mapping.name: mapping for mapping in project.mappings if not mapping.deploy}
    assert {mapping.name for mapping in deployed} == {
        "WriteSetpoint", "Batch_FC03_10_12", "Batch_FC01_20_20"
    }
    assert aliases["OutsideTemp"].symbol_data_type == "float32"
    assert aliases["OutsideTemp"].register == 1025
    assert aliases["Setpoint"].register == 1027

    symbols = export_atvise_symbols(project)
    assert "sym-OutsideTemp=HRR1025," in symbols
    assert "sym-Setpoint=HR1027," in symbols
    assert "sym-Alarm=DA1025," in symbols
    assert "Batch_FC" not in symbols

    generated = generate_uci(project)
    assert generated.modbus_client.count("config request_") == 3
    assert generated.modbus_server.count("config tag ") == 3


def test_auto_plan_skips_writes_and_ambiguous_multi_value_mappings():
    project = _project()
    project.mappings[1].count = 4
    plan = build_existing_batch_plan(
        project,
        device_name="PLC",
        request_names=[request.name for request in project.tcp_clients[0].requests],
    )

    assert plan.original_request_names == ["OutsideTemp", "Alarm"]
    assert any("Setpoint: mapping count 4" in item for item in plan.skipped)
    assert any("WriteSetpoint: FC06 is not a read request" in item for item in plan.skipped)


def test_allocator_ignores_symbol_only_aliases_when_placing_new_batches():
    project = _project()
    project.mappings.append(ServerMapping(
        "OldAlias", "PLC", "OldBatch", 5000, "holding_register", deploy=False
    ))

    plan = build_existing_batch_plan(
        project, device_name="PLC", request_names=["OutsideTemp", "Setpoint"]
    )

    assert plan.block_mappings[0].register == 1025
