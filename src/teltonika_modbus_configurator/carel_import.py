"""Carel cDesign Modbus export inspection helpers.

The normalized preview pipeline is intentionally format-independent: legacy
`.xls`, modern `.xlsx`, and `.csv` inputs are reduced to plain rows first, then
run through the same header detection and normalization logic.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(slots=True)
class CarelImportRow:
    sheet: str
    row_number: int
    name: str = ""
    register: str = ""
    modbus_type: str = ""
    size: str = ""
    data_type: str = ""
    access: str = ""
    raw: tuple[str, ...] = ()


@dataclass(slots=True)
class CarelImportPreview:
    path: str
    sheets: list[str]
    header_row: int | None
    headers: list[str]
    rows: list[CarelImportRow]


_NAME_ALIASES = ("variable name", "variable acronym", "name", "variable", "symbol", "tag", "parameter")
_REGISTER_ALIASES = ("index", "register", "address", "addr", "modbus address")
_MODBUS_TYPE_ALIASES = ("types", "modbus type", "register type", "area")
_SIZE_ALIASES = ("size", "length", "count")
_DATA_TYPE_ALIASES = ("datatype", "data type", "type", "format")
_ACCESS_ALIASES = ("direction", "access", "read/write", "r/w", "permission", "mode")


def sanitize_carel_name(value: str) -> str:
    """Convert a cDesign variable path to a RutOS/SCADA-friendly name."""
    name = value.strip().replace(".", "_")
    return name.replace("[", "").replace("]", "")


def _text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _column_for(headers: list[str], aliases: tuple[str, ...], *, allow_contains: bool = True) -> int | None:
    normalized = [_norm(h) for h in headers]
    normalized_aliases = [_norm(alias) for alias in aliases]
    for alias in normalized_aliases:
        for i, header in enumerate(normalized):
            if header == alias:
                return i
    if allow_contains:
        for alias in normalized_aliases:
            if len(alias) < 4:
                continue
            for i, header in enumerate(normalized):
                if alias in header:
                    return i
    return None


def detect_header_row(rows: list[list[object]], max_scan: int = 60) -> int | None:
    best: tuple[int, int] | None = None
    for idx, row in enumerate(rows[:max_scan]):
        headers = [_text(v) for v in row]
        score = 0
        if _column_for(headers, _NAME_ALIASES) is not None:
            score += 3
        if _column_for(headers, _REGISTER_ALIASES) is not None:
            score += 3
        if _column_for(headers, _MODBUS_TYPE_ALIASES) is not None:
            score += 2
        if _column_for(headers, _DATA_TYPE_ALIASES) is not None:
            score += 1
        if _column_for(headers, _ACCESS_ALIASES) is not None:
            score += 1
        if sum(bool(h) for h in headers) >= 3:
            score += 1
        if score and (best is None or score > best[0]):
            best = (score, idx)
    return None if best is None or best[0] < 4 else best[1]


def preview_rows(sheet_name: str, rows: list[list[object]]) -> tuple[int | None, list[str], list[CarelImportRow]]:
    header_idx = detect_header_row(rows)
    if header_idx is None:
        return None, [], []

    headers = [_text(v) for v in rows[header_idx]]
    name_col = _column_for(headers, _NAME_ALIASES)
    reg_col = _column_for(headers, _REGISTER_ALIASES)
    modbus_type_col = _column_for(headers, _MODBUS_TYPE_ALIASES)
    size_col = _column_for(headers, _SIZE_ALIASES)
    data_type_col = _column_for(headers, _DATA_TYPE_ALIASES)
    access_col = _column_for(headers, _ACCESS_ALIASES)

    result: list[CarelImportRow] = []
    for excel_row, raw_row in enumerate(rows[header_idx + 1 :], start=header_idx + 2):
        raw = tuple(_text(v) for v in raw_row)
        if not any(raw):
            continue

        def val(index: int | None) -> str:
            return raw[index] if index is not None and index < len(raw) else ""

        name = sanitize_carel_name(val(name_col))
        register = val(reg_col)
        if not name and not register:
            continue
        result.append(
            CarelImportRow(
                sheet=sheet_name,
                row_number=excel_row,
                name=name,
                register=register,
                modbus_type=val(modbus_type_col),
                size=val(size_col),
                data_type=val(data_type_col),
                access=val(access_col),
                raw=raw,
            )
        )
    return header_idx + 1, headers, result


def _preview_from_sheets(path: str | Path, sheets: list[tuple[str, list[list[object]]]]) -> CarelImportPreview:
    best = None
    sheet_names = [name for name, _ in sheets]
    for sheet_name, rows in sheets:
        header_row, headers, parsed = preview_rows(sheet_name, rows)
        candidate = (len(parsed), header_row, headers, parsed)
        if best is None or candidate[0] > best[0]:
            best = candidate
    if best is None:
        return CarelImportPreview(str(path), sheet_names, None, [], [])
    _, header_row, headers, parsed = best
    return CarelImportPreview(str(path), sheet_names, header_row, headers, parsed)


def load_carel_xls(path: str | Path) -> CarelImportPreview:
    """Read a legacy Carel cDesign `.xls` export using xlrd."""
    try:
        import xlrd
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Carel .xls import requires the 'xlrd' package.") from exc

    workbook = xlrd.open_workbook(str(path), on_demand=True)
    sheets = []
    for sheet_name in workbook.sheet_names():
        sheet = workbook.sheet_by_name(sheet_name)
        sheets.append((sheet_name, [sheet.row_values(i) for i in range(sheet.nrows)]))
    return _preview_from_sheets(path, sheets)


def load_carel_xlsx(path: str | Path) -> CarelImportPreview:
    """Read a modern Excel `.xlsx` export using openpyxl in read-only mode."""
    try:
        from openpyxl import load_workbook
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Carel .xlsx import requires the 'openpyxl' package.") from exc

    workbook = load_workbook(filename=str(path), read_only=True, data_only=True)
    sheets = []
    for sheet in workbook.worksheets:
        rows = [list(row) for row in sheet.iter_rows(values_only=True)]
        sheets.append((sheet.title, rows))
    workbook.close()
    return _preview_from_sheets(path, sheets)


def load_carel_csv(path: str | Path) -> CarelImportPreview:
    """Read a CSV export with automatic delimiter sniffing."""
    text = Path(path).read_text(encoding="utf-8-sig")
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows = [list(row) for row in csv.reader(text.splitlines(), dialect)]
    return _preview_from_sheets(path, [("CSV", rows)])


def load_carel_file(path: str | Path) -> CarelImportPreview:
    """Load a supported Carel export based on file extension."""
    suffix = Path(path).suffix.lower()
    if suffix == ".xls":
        return load_carel_xls(path)
    if suffix == ".xlsx":
        return load_carel_xlsx(path)
    if suffix == ".csv":
        return load_carel_csv(path)
    raise ValueError(f"Unsupported Carel import format {suffix or '<none>'}. Use .xls, .xlsx, or .csv.")
