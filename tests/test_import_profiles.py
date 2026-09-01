from teltonika_modbus_configurator.carel_import import detect_header_row, preview_rows
from teltonika_modbus_configurator.import_profiles import CAREL_CDESIGN, ImportProfile, get_import_profile


def test_builtin_carel_profile_is_registered():
    profile = get_import_profile("carel_cdesign")
    assert profile is CAREL_CDESIGN
    assert profile.default_add_one_to_index is True


def test_custom_profile_can_use_different_column_names():
    profile = ImportProfile(
        key="example",
        label="Example vendor",
        name_aliases=("point",),
        register_aliases=("offset",),
        modbus_type_aliases=("memory",),
        size_aliases=("words",),
        data_type_aliases=("encoding",),
        access_aliases=("rights",),
        sanitize_name=lambda value: value.strip().replace("/", "_"),
    )
    rows = [
        ["Example register list"],
        ["Memory", "Offset", "Words", "Point", "Encoding", "Rights"],
        ["HoldingRegister", 42, 1, "Plant/Setpoint", "UInt", "RW"],
    ]

    assert detect_header_row(rows, profile=profile) == 1
    header_row, _, parsed = preview_rows("Sheet1", rows, profile=profile)

    assert header_row == 2
    assert len(parsed) == 1
    assert parsed[0].name == "Plant_Setpoint"
    assert parsed[0].register == "42"
    assert parsed[0].modbus_type == "HoldingRegister"
    assert parsed[0].data_type == "UInt"
    assert parsed[0].access == "RW"


def test_carel_profile_keeps_cdesign_name_rules():
    rows = [
        ["Types", "Index", "Variable Name", "DataType", "Direction"],
        ["HoldingRegister", 10, "Scheduler.Event_Msk[1].Enabled", "UInt", "ReadWrite"],
    ]
    _, _, parsed = preview_rows("Documentation", rows, profile=CAREL_CDESIGN)
    assert parsed[0].name == "Scheduler_Event_Msk1_Enabled"
