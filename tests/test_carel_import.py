from pathlib import Path

from openpyxl import Workbook

from teltonika_modbus_configurator.carel_import import (
    detect_header_row,
    load_carel_file,
    preview_rows,
    sanitize_carel_name,
)


def _cdesign_rows():
    return [
        ["Types", "Index", "Size", "Variable Name", "DataType", "Direction"],
        ["HoldingRegister", 240, 2, "AI.U5[1]", "Real", "ReadWrite"],
        ["Coil", 10, 1, "VKLOP.SISTEMA", "Bool", "ReadWrite"],
    ]


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


def test_cdesign_documentation_columns_are_not_confused():
    rows = [[
        "Types", "Index", "Size", "Variable Name", "Variable Acronym",
        "Variable Description", "DataType", "Default Value", "Min", "Max", "UoM", "Direction",
    ], ["HoldingRegister", 240.0, 2.0, "AI_U5_ZunTemp", "U5", "Outside temp", "REAL", 0, -50, 100, "degC", "R"],
        ["Coil", 10.0, 1.0, "NO1_Crpalka_Klimati_AR", "NO1", "Pump auto/manual", "BOOL", 0, 0, 1, "", "RW"]]
    header_row, _, parsed = preview_rows("Documentation", rows)
    assert header_row == 1
    assert parsed[0].name == "AI_U5_ZunTemp"
    assert parsed[0].register == "240"
    assert parsed[0].modbus_type == "HoldingRegister"
    assert parsed[0].size == "2"
    assert parsed[0].data_type == "REAL"
    assert parsed[0].access == "R"
    assert parsed[1].modbus_type == "Coil"
    assert parsed[1].data_type == "BOOL"
    assert parsed[1].access == "RW"


def test_sanitize_carel_name_replaces_dots_and_removes_array_brackets():
    assert sanitize_carel_name("Klimati.Scheduler_1.Event_Msk[1].Enabled") == "Klimati_Scheduler_1_Event_Msk1_Enabled"
    assert sanitize_carel_name("Msk[1]") == "Msk1"


def test_preview_uses_sanitized_variable_name():
    rows = [
        ["Types", "Index", "Size", "Variable Name", "DataType", "Direction"],
        ["HoldingRegister", 10, 1, "Scheduler.Event_Msk[1].Enabled", "UInt", "ReadWrite"],
    ]
    _, _, parsed = preview_rows("Documentation", rows)
    assert parsed[0].name == "Scheduler_Event_Msk1_Enabled"


def test_requires_name_or_register_columns_for_header_detection():
    rows = [
        ["Description", "Unit", "Minimum", "Maximum"],
        ["Outside temperature", "degC", -40, 80],
    ]
    assert detect_header_row(rows) is None


def test_load_carel_csv_with_semicolon_delimiter(tmp_path: Path):
    path = tmp_path / "carel.csv"
    path.write_text(
        "Types;Index;Size;Variable Name;DataType;Direction\n"
        "HoldingRegister;240;2;AI.U5[1];Real;ReadWrite\n"
        "Coil;10;1;VKLOP.SISTEMA;Bool;ReadWrite\n",
        encoding="utf-8",
    )
    preview = load_carel_file(path)
    assert preview.sheets == ["CSV"]
    assert [row.name for row in preview.rows] == ["AI_U51", "VKLOP_SISTEMA"]
    assert preview.rows[0].register == "240"
    assert preview.rows[0].data_type == "Real"


def test_load_carel_xlsx_uses_same_normalized_pipeline(tmp_path: Path):
    path = tmp_path / "carel.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Documentation"
    for row in _cdesign_rows():
        sheet.append(row)
    workbook.save(path)

    preview = load_carel_file(path)
    assert preview.sheets == ["Documentation"]
    assert len(preview.rows) == 2
    assert preview.rows[0].name == "AI_U51"
    assert preview.rows[0].modbus_type == "HoldingRegister"
    assert preview.rows[1].name == "VKLOP_SISTEMA"


def test_load_carel_file_rejects_unknown_extension(tmp_path: Path):
    path = tmp_path / "carel.txt"
    path.write_text("anything", encoding="utf-8")
    try:
        load_carel_file(path)
    except ValueError as exc:
        assert ".xls, .xlsx, or .csv" in str(exc)
    else:
        raise AssertionError("Unsupported extension should be rejected")
