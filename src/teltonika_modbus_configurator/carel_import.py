"""Carel cDesign Modbus export inspection helpers.

v0.4 starts with a non-destructive preview step: read the native legacy .xls
export, locate likely header rows, and normalize candidate register records.
Nothing is added to the project until the detected structure has been verified
against a real cDesign export.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(slots=True)
class CarelImportRow:
    sheet: str
    row_number: int
    name: str = ""
    register: str = ""
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


_NAME_ALIASES = ("name", "variable", "symbol", "tag", "parameter")
_REGISTER_ALIASES = ("register", "address", "addr", "modbus")
_TYPE_ALIASES = ("type", "datatype", "data type", "format")
_ACCESS_ALIASES = ("access", "read/write", "r/w", "permission", "mode")


def _text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _column_for(headers: list[str], aliases: tuple[str, ...]) -> int | None:
    normalized = [_norm(h) for h in headers]
    for alias in aliases:
        a = _norm(alias)
        for i, header in enumerate(normalized):
            if header == a or a in header:
                return i
    return None


def detect_header_row(rows: list[list[object]], max_scan: int = 60) -> int | None:
    """Return the most plausible table-header row index, or None."""
    best: tuple[int, int] | None = None
    for idx, row in enumerate(rows[:max_scan]):
        headers = [_text(v) for v in row]
        score = 0
        if _column_for(headers, _NAME_ALIASES) is not None:
            score += 3
        if _column_for(headers, _REGISTER_ALIASES) is not None:
            score += 3
        if _column_for(headers, _TYPE_ALIASES) is not None:
            score += 1
        if _column_for(headers, _ACCESS_ALIASES) is not None:
            score += 1
        nonempty = sum(bool(h) for h in headers)
        if nonempty >= 3:
            score += 1
        if score and (best is None or score > best[0]):
            best = (score, idx)
    return None if best is None or best[0] < 4 else best[1]


def preview_rows(sheet_name: str, rows: list[list[object]]) -> tuple[int | None, list[str], list[CarelImportRow]]:
    """Normalize one worksheet represented as plain row values."""
    header_idx = detect_header_row(rows)
    if header_idx is None:
        return None, [], []

    headers = [_text(v) for v in rows[header_idx]]
    name_col = _column_for(headers, _NAME_ALIASES)
    reg_col = _column_for(headers, _REGISTER_ALIASES)
    type_col = _column_for(headers, _TYPE_ALIASES)
    access_col = _column_for(headers, _ACCESS_ALIASES)

    result: list[CarelImportRow] = []
    for excel_row, raw_row in enumerate(rows[header_idx + 1 :], start=header_idx + 2):
        raw = tuple(_text(v) for v in raw_row)
        if not any(raw):
            continue

        def val(index: int | None) -> str:
            return raw[index] if index is not None and index < len(raw) else ""

        name = val(name_col)
        register = val(reg_col)
        if not name and not register:
            continue
        result.append(
            CarelImportRow(
                sheet=sheet_name,
                row_number=excel_row,
                name=name,
                register=register,
                data_type=val(type_col),
                access=val(access_col),
                raw=raw,
            )
        )
    return header_idx + 1, headers, result


def load_carel_xls(path: str | Path) -> CarelImportPreview:
    """Read a legacy Carel cDesign .xls export using xlrd."""
    try:
        import xlrd
    except ImportError as exc:  # pragma: no cover - packaging installs dependency
        raise RuntimeError("Carel .xls import requires the 'xlrd' package.") from exc

    workbook = xlrd.open_workbook(str(path), on_demand=True)
    best = None
    sheet_names = workbook.sheet_names()
    for sheet_name in sheet_names:
        sheet = workbook.sheet_by_name(sheet_name)
        rows = [sheet.row_values(i) for i in range(sheet.nrows)]
        header_row, headers, parsed = preview_rows(sheet_name, rows)
        candidate = (len(parsed), header_row, headers, parsed)
        if best is None or candidate[0] > best[0]:
            best = candidate

    if best is None:
        return CarelImportPreview(str(path), sheet_names, None, [], [])
    _, header_row, headers, parsed = best
    return CarelImportPreview(str(path), sheet_names, header_row, headers, parsed)
