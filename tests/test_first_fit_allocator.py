from teltonika_modbus_configurator.bulk import allocate_template_mapping_layout
from teltonika_modbus_configurator.models import Project, ServerMapping
from teltonika_modbus_configurator.register_allocator import first_free_register_range


def _mapping(name, device, request, register, register_type, data_type="int16", count=1):
    return ServerMapping(
        name=name,
        device=device,
        request=request,
        register=register,
        register_type=register_type,
        data_type=data_type,
        count=count,
    )


def test_first_fit_uses_gap_before_later_float32_mapping():
    project = Project(
        mappings=[
            _mapping("CMD_Oper_Mode", "RDF_Test", "CMD_Oper_Mode", 1031, "holding_register"),
            _mapping("CMD_Fan_Speed", "RDF_Test", "CMD_Fan_Speed", 1032, "holding_register"),
            _mapping("CMD_Temp_SetP", "RDF_Test", "CMD_Temp_SetP", 1033, "holding_register"),
            _mapping("AI_U5_ZunTemp", "Carel_Test", "AI_U5_ZunTemp", 1100, "holding_register", "float32"),
        ]
    )

    assert first_free_register_range(
        project, register_type="holding_register", width=3, default=1031
    ) == 1034


def test_template_layout_fills_gap_instead_of_jumping_above_carel():
    rdf = [
        _mapping("CMD_Oper_Mode", "RDF_Test", "CMD_Oper_Mode", 1031, "holding_register"),
        _mapping("CMD_Fan_Speed", "RDF_Test", "CMD_Fan_Speed", 1032, "holding_register"),
        _mapping("CMD_Temp_SetP", "RDF_Test", "CMD_Temp_SetP", 1033, "holding_register"),
    ]
    project = Project(
        mappings=rdf + [
            _mapping("AI_U5_ZunTemp", "Carel_Test", "AI_U5_ZunTemp", 1100, "holding_register", "float32"),
        ]
    )

    layout = allocate_template_mapping_layout(project, rdf)

    assert layout["CMD_Oper_Mode"] == (1034, 3)
    assert layout["CMD_Fan_Speed"] == (1035, 3)
    assert layout["CMD_Temp_SetP"] == (1036, 3)


def test_float32_still_reserves_two_registers_during_first_fit():
    project = Project(
        mappings=[
            _mapping("Float", "Carel", "Float", 1034, "holding_register", "float32"),
            _mapping("Later", "Other", "Later", 1037, "holding_register"),
        ]
    )

    # 1034-1035 are occupied by float32, 1036 is only one register wide, so a
    # two-register block cannot fit until 1038.
    assert first_free_register_range(
        project, register_type="holding_register", width=2, default=1034
    ) == 1038
