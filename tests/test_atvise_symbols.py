import pytest

from teltonika_modbus_configurator.atvise_symbols import (
    AtviseSymbolExportError,
    export_atvise_symbols,
)
from teltonika_modbus_configurator.models import Project, ServerMapping


def _mapping(name, register, register_type, data_type="int16", enabled=True):
    return ServerMapping(
        name=name,
        device="D1",
        request="R1",
        register=register,
        register_type=register_type,
        enabled=enabled,
        data_type=data_type,
    )


def test_exports_verified_atvise_prefixes():
    project = Project(
        mappings=[
            _mapping("Status_Temp", 1025, "input_register", "int16"),
            _mapping("Cmd_Setpoint", 1080, "holding_register", "uint16"),
            _mapping("Door", 1100, "discrete_input", "bool"),
            _mapping("Pump", 1101, "coil", "bool"),
            _mapping("Pressure", 1200, "input_register", "float32"),
            _mapping("FloatCommand", 1202, "holding_register", "float32"),
            _mapping("SchedulerDay", 1204, "holding_register", "int32"),
            _mapping("PulseCounter", 1206, "holding_register", "uint32"),
        ]
    )

    assert export_atvise_symbols(project) == (
        "[]\n"
        "[D1]\n"
        "sym-Status_Temp=IR1025,\n"
        "sym-Cmd_Setpoint=HR1080,\n"
        "sym-Door=DI1100,\n"
        "sym-Pump=DA1101,\n"
        "sym-Pressure=IRR1200,\n"
        "sym-FloatCommand=HRR1202,\n"
        "sym-SchedulerDay=HRD1204,\n"
        "sym-PulseCounter=HRD1206,\n"
    )


def test_disabled_mapping_is_omitted_by_default():
    project = Project(
        mappings=[
            _mapping("Visible", 1025, "input_register", enabled=True),
            _mapping("Hidden", 1026, "input_register", enabled=False),
        ]
    )
    text = export_atvise_symbols(project)
    assert "Visible" in text
    assert "Hidden" not in text


def test_can_include_disabled_mapping_explicitly():
    project = Project(mappings=[_mapping("Hidden", 1025, "input_register", enabled=False)])
    assert "sym-Hidden=IR1025," in export_atvise_symbols(project, include_disabled=True)


def test_semantic_symbol_datatype_can_differ_from_raw_server_tag():
    mapping = _mapping("Temperature", 1025, "holding_register", "uint16")
    mapping.count = 2
    mapping.symbol_data_type = "float32"
    assert "sym-Temperature=HRR1025," in export_atvise_symbols(Project(mappings=[mapping]))


def test_physical_block_mapping_can_be_excluded_from_symbol_export():
    mapping = _mapping("Batch", 1025, "holding_register", "uint16")
    mapping.export_symbol = False
    assert export_atvise_symbols(Project(mappings=[mapping])) == "[]\n"


def test_groups_symbols_by_source_device_and_supports_custom_group_names():
    from teltonika_modbus_configurator.models import Device

    project = Project(
        devices=[
            Device("Boiler", 1, "RS485", symbol_group="Plant_room"),
            Device("Heating", 2, "RS485"),
        ],
        mappings=[
            ServerMapping("BoilerTemp", "Boiler", "R1", 1025, "holding_register"),
            ServerMapping("RoomTemp", "Heating", "R1", 1026, "holding_register"),
            ServerMapping("BoilerSetpoint", "Boiler", "R2", 1027, "holding_register"),
        ],
    )

    assert export_atvise_symbols(project) == (
        "[]\n"
        "[Plant_room]\n"
        "sym-BoilerTemp=HR1025,\n"
        "sym-BoilerSetpoint=HR1027,\n"
        "[Heating]\n"
        "sym-RoomTemp=HR1026,\n"
    )


def test_can_export_legacy_flat_symbol_file():
    project = Project(mappings=[_mapping("Temperature", 1025, "holding_register")])
    assert export_atvise_symbols(project, group_by_device=False) == "[]\nsym-Temperature=HR1025,\n"


def test_rejects_physical_batches_when_symbol_aliases_are_missing():
    project = Project(mappings=[
        ServerMapping(
            "Batch_FC03_1_100", "PLC", "Batch_FC03_1_100", 1025,
            "holding_register", count=100, data_type="uint16",
        )
    ])

    with pytest.raises(AtviseSymbolExportError, match="saved project YAML"):
        export_atvise_symbols(project)


def test_rejects_live_imported_multi_value_block_with_nonstandard_batch_name():
    project = Project(mappings=[
        ServerMapping(
            "Status_Batch", "RDF_Test", "Status_Batch", 1025,
            "input_register", count=6, data_type="int16",
        )
    ])

    with pytest.raises(AtviseSymbolExportError, match="symbol aliases"):
        export_atvise_symbols(project)


def test_rejects_unsafe_symbol_group():
    from teltonika_modbus_configurator.models import Device

    project = Project(
        devices=[Device("D1", 1, "RS485", symbol_group="Bad[group")],
        mappings=[_mapping("Temperature", 1025, "holding_register")],
    )
    with pytest.raises(AtviseSymbolExportError, match="unsafe"):
        export_atvise_symbols(project)


@pytest.mark.parametrize(
    ("register_type", "data_type"),
    [
        ("input_register", "int32"),
        ("input_register", "uint32"),
        ("input_register", "float64"),
        ("holding_register", "float64"),
    ],
)
def test_rejects_unverified_atvise_encodings(register_type, data_type):
    project = Project(mappings=[_mapping("Unknown", 1200, register_type, data_type)])
    with pytest.raises(AtviseSymbolExportError, match="has not been verified yet"):
        export_atvise_symbols(project)
