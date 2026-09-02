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
        ]
    )

    assert export_atvise_symbols(project) == (
        "[]\n"
        "sym-Status_Temp=IR1025,\n"
        "sym-Cmd_Setpoint=HR1080,\n"
        "sym-Door=DI1100,\n"
        "sym-Pump=DA1101,\n"
        "sym-Pressure=IRR1200,\n"
        "sym-FloatCommand=HRR1202,\n"
        "sym-SchedulerDay=HRD1204,\n"
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


@pytest.mark.parametrize(
    ("register_type", "data_type"),
    [
        ("input_register", "int32"),
        ("holding_register", "uint32"),
        ("input_register", "float64"),
        ("holding_register", "float64"),
    ],
)
def test_rejects_unverified_atvise_encodings(register_type, data_type):
    project = Project(mappings=[_mapping("Unknown", 1200, register_type, data_type)])
    with pytest.raises(AtviseSymbolExportError, match="has not been verified yet"):
        export_atvise_symbols(project)
