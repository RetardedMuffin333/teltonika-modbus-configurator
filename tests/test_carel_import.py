from teltonika_modbus_configurator.carel_import import detect_header_row, preview_rows


def test_detects_register_table_after_title_rows():
    rows = [
        ["Carel", "Documentation Excel file"],
        ["Project", "Example"],
        [],
        ["Variable name", "Modbus address", "Data type", "Read/Write"],
        ["AI_U5_ZunTemp", 240, "FLOAT32", "R"],
    ]
    assert detect_header_row(rows) == 3


def test_preview_normalizes_candidate_rows():
    rows = [
        ["Carel export"],
        ["Variable", "Register", "Type", "Access"],
        ["AI_U5_ZunTemp", 240.0, "FLOAT32", "Read"],
        ["CMD_Mode", 101.0, "INT16", "Read/Write"],
    ]
    header_row, headers, parsed = preview_rows("Modbus", rows)

    assert header_row == 2
    assert headers == ["Variable", "Register", "Type", "Access"]
    assert [row.name for row in parsed] == ["AI_U5_ZunTemp", "CMD_Mode"]
    assert [row.register for row in parsed] == ["240", "101"]
    assert parsed[0].data_type == "FLOAT32"
    assert parsed[1].access == "Read/Write"


def test_requires_name_or_register_columns_for_header_detection():
    rows = [
        ["Description", "Unit", "Minimum", "Maximum"],
        ["Outside temperature", "degC", -40, 80],
    ]
    assert detect_header_row(rows) is None
