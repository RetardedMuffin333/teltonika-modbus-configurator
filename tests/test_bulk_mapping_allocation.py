from teltonika_modbus_configurator.bulk import (
    BulkMappingSpec,
    BulkRequestSpec,
    BulkSpec,
    allocate_template_mapping_layout,
    generate_bulk,
    validate_bulk_spec,
)
from teltonika_modbus_configurator.models import (
    Device,
    FunctionCode,
    Project,
    Request,
    SerialConnection,
    ServerMapping,
)
from teltonika_modbus_configurator.register_allocator import mapping_width


def _rdf_project() -> Project:
    requests = [
        Request("Status_Room_Temp", FunctionCode.READ_INPUT_REGISTERS, 5),
        Request("Status_Oper_Mode", FunctionCode.READ_INPUT_REGISTERS, 4),
        Request("Status_Temp_SetP", FunctionCode.READ_INPUT_REGISTERS, 6),
        Request("CMD_Oper_Mode", FunctionCode.READ_HOLDING_REGISTERS, 101),
        Request("CMD_Fan_Speed", FunctionCode.READ_HOLDING_REGISTERS, 103),
        Request("CMD_Temp_SetP", FunctionCode.READ_HOLDING_REGISTERS, 104),
    ]
    device = Device("RDF_Test", 1, "RDF400MB", requests=requests)
    mappings = [
        ServerMapping("Status_Room_Temp", "RDF_Test", "Status_Room_Temp", 1025, "input_register"),
        ServerMapping("Status_Oper_Mode", "RDF_Test", "Status_Oper_Mode", 1026, "input_register"),
        ServerMapping("Status_Temp_SetP", "RDF_Test", "Status_Temp_SetP", 1027, "input_register"),
        ServerMapping("CMD_Oper_Mode", "RDF_Test", "CMD_Oper_Mode", 1031, "holding_register"),
        ServerMapping("CMD_Fan_Speed", "RDF_Test", "CMD_Fan_Speed", 1032, "holding_register"),
        ServerMapping("CMD_Temp_SetP", "RDF_Test", "CMD_Temp_SetP", 1033, "holding_register"),
    ]
    return Project(connections=[SerialConnection(name="RDF400MB")], devices=[device], mappings=mappings)


def test_template_layout_allocates_whole_blocks_after_existing_ranges():
    project = _rdf_project()
    source = list(project.mappings)
    layout = allocate_template_mapping_layout(project, source)

    assert layout["Status_Room_Temp"] == (1028, 3)
    assert layout["Status_Oper_Mode"] == (1029, 3)
    assert layout["Status_Temp_SetP"] == (1030, 3)
    assert layout["CMD_Oper_Mode"] == (1034, 3)
    assert layout["CMD_Fan_Speed"] == (1035, 3)
    assert layout["CMD_Temp_SetP"] == (1036, 3)


def test_two_generated_devices_from_allocated_layout_do_not_overlap():
    project = _rdf_project()
    layout = allocate_template_mapping_layout(project, list(project.mappings))
    requests = [
        BulkRequestSpec("Status_Room_Temp", FunctionCode.READ_INPUT_REGISTERS, 5),
        BulkRequestSpec("Status_Oper_Mode", FunctionCode.READ_INPUT_REGISTERS, 4),
        BulkRequestSpec("Status_Temp_SetP", FunctionCode.READ_INPUT_REGISTERS, 6),
        BulkRequestSpec("CMD_Oper_Mode", FunctionCode.READ_HOLDING_REGISTERS, 101),
        BulkRequestSpec("CMD_Fan_Speed", FunctionCode.READ_HOLDING_REGISTERS, 103),
        BulkRequestSpec("CMD_Temp_SetP", FunctionCode.READ_HOLDING_REGISTERS, 104),
    ]
    source_by_request = {m.request: m for m in project.mappings}
    mappings = []
    for request in requests:
        source = source_by_request[request.name]
        start, step = layout[source.name]
        mappings.append(BulkMappingSpec(
            f"{{device}}_{request.name}", request.name, source.register_type,
            start, step=step, data_type=source.data_type, count=source.count,
        ))
    spec = BulkSpec(
        connection="RDF400MB", name_pattern="RDF_Test_{index:02d}", count=2,
        start_index=2, slave_start=2, requests=requests, mappings=mappings,
    )

    assert validate_bulk_spec(project, spec) == []
    result = generate_bulk(project, spec)
    input_regs = [m.register for m in result.mappings if m.register_type == "input_register"]
    holding_regs = [m.register for m in result.mappings if m.register_type == "holding_register"]
    assert input_regs == [1028, 1029, 1030, 1031, 1032, 1033]
    assert holding_regs == [1034, 1035, 1036, 1037, 1038, 1039]


def test_float32_mapping_reserves_two_modbus_registers():
    mapping = ServerMapping(
        "OutsideTemp", "Carel", "AI_U5_ZunTemp", 1100, "holding_register",
        data_type="float32", count=1,
    )
    assert mapping_width(mapping) == 2


def test_bulk_template_preserves_batch_aliases_without_duplicate_live_ranges():
    project = Project(
        connections=[SerialConnection(name="RS485")],
        devices=[Device(
            "Template", 1, "RS485",
            requests=[Request("Batch_HR_10_19", FunctionCode.READ_HOLDING_REGISTERS, 10, count=10)],
        )],
        mappings=[
            ServerMapping(
                "Batch_HR_10_19", "Template", "Batch_HR_10_19", 1025,
                "holding_register", data_type="uint16", count=10, export_symbol=False,
            ),
            ServerMapping(
                "Room_Temperature", "Template", "Batch_HR_10_19", 1027,
                "holding_register", data_type="uint16", count=2, source_offset=2,
                symbol_data_type="float32", deploy=False,
            ),
            ServerMapping(
                "Mode", "Template", "Batch_HR_10_19", 1030,
                "holding_register", data_type="uint16", source_offset=5,
                symbol_data_type="uint16", deploy=False,
            ),
        ],
    )
    layout = allocate_template_mapping_layout(project, project.mappings)
    specs = [
        BulkMappingSpec(
            name_pattern=f"{{device}}_{mapping.name}", request=mapping.request,
            register_type=mapping.register_type, start_register=layout[mapping.name][0],
            step=layout[mapping.name][1], data_type=mapping.data_type, count=mapping.count,
            source_offset=mapping.source_offset, symbol_data_type=mapping.symbol_data_type,
            deploy=mapping.deploy, export_symbol=mapping.export_symbol,
        )
        for mapping in project.mappings
    ]
    spec = BulkSpec(
        connection="RS485", name_pattern="Clone{index}", count=2,
        start_index=2, slave_start=2,
        requests=[BulkRequestSpec("Batch_HR_10_19", FunctionCode.READ_HOLDING_REGISTERS, 10, count=10)],
        mappings=specs,
    )

    assert validate_bulk_spec(project, spec) == []
    result = generate_bulk(project, spec)
    assert len([mapping for mapping in result.mappings if mapping.deploy]) == 2
    assert len([mapping for mapping in result.mappings if not mapping.deploy]) == 4
    aliases = [mapping for mapping in result.mappings if not mapping.deploy]
    assert {mapping.source_offset for mapping in aliases} == {2, 5}
    assert {mapping.symbol_data_type for mapping in aliases} == {"float32", "uint16"}


def test_bulk_template_alias_name_pattern_uses_symbol_name_not_shared_batch_request():
    from teltonika_modbus_configurator.gui_bulk import BulkGeneratorWindow

    assert BulkGeneratorWindow._suggest_mapping_pattern(
        "Room_Temperature", "Template"
    ) == "{device}_Room_Temperature"
    assert BulkGeneratorWindow._suggest_mapping_pattern(
        "Template_Batch_HR_10_19", "Template"
    ) == "{device}_Batch_HR_10_19"
