from teltonika_modbus_configurator.atvise_symbols import (
    AtviseSymbolExportError,
    export_atvise_symbols,
)
from teltonika_modbus_configurator.models import Project, ServerMapping


def test_exports_ir_and_hr_in_connect_symbol_format():
    project = Project(
        mappings=[
            ServerMapping("Status_Temp01", "Joy01", "IR", 1025, "input_register", True),
            ServerMapping("Cmd_Basic_Setpoint", "Joy01", "HR", 1080, "holding_register", True),
        ]
    )

    assert export_atvise_symbols(project) == (
        "[]\n"
        "sym-Status_Temp01=IR1025,\n"
        "sym-Cmd_Basic_Setpoint=HR1080,\n"
    )


def test_disabled_mapping_is_omitted_by_default():
    project = Project(
        mappings=[
            ServerMapping("Visible", "D1", "R", 100, "input_register", True),
            ServerMapping("Hidden", "D1", "R", 101, "input_register", False),
        ]
    )
    text = export_atvise_symbols(project)
    assert "Visible" in text
    assert "Hidden" not in text


def test_can_include_disabled_mapping_explicitly():
    project = Project(
        mappings=[ServerMapping("Hidden", "D1", "R", 101, "input_register", False)]
    )
    assert "sym-Hidden=IR101," in export_atvise_symbols(project, include_disabled=True)


def test_v1_rejects_unverified_register_types():
    project = Project(
        mappings=[ServerMapping("Coil01", "D1", "R", 1, "coil", True)]
    )
    try:
        export_atvise_symbols(project)
    except AtviseSymbolExportError as exc:
        assert "supports only input_register and holding_register" in str(exc)
    else:
        raise AssertionError("Expected AtviseSymbolExportError")
