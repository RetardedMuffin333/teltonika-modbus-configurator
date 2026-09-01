"""Import atvise Connect .Symbol node/register lists.

Symbol files describe node names and Modbus addresses, not connection settings.
The caller therefore selects an existing RTU or TCP client as the import target.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import re

from .models import FunctionCode, Project, Request, ServerMapping
from .register_allocator import first_free_register_range, register_value_width


@dataclass(slots=True)
class SymbolRow:
    line_number: int
    name: str
    symbol_type: str
    register: int
    raw: str = ""


@dataclass(slots=True)
class SymbolPreview:
    path: str
    rows: list[SymbolRow]
    ignored_lines: int = 0


@dataclass(slots=True)
class SymbolPlannedItem:
    source: SymbolRow
    request: Request | None
    mapping: ServerMapping | None
    status: str


# Verified against real atvise Connect symbols and live/working RutOS requests.
# Tuple: function, TCP register type, normalized data type, byte order, RutOS reg_count.
# HRD is Carel/atvise DINT: FC03, signed 32-bit 1234, and requires reg_count=2.
_SYMBOL_MAP = {
    "IR": (FunctionCode.READ_INPUT_REGISTERS, "input_register", "int16", "high_byte_first", 1),
    "IRR": (FunctionCode.READ_INPUT_REGISTERS, "input_register", "float32", "1234", 1),
    "HR": (FunctionCode.READ_HOLDING_REGISTERS, "holding_register", "int16", "high_byte_first", 1),
    "HRR": (FunctionCode.READ_HOLDING_REGISTERS, "holding_register", "float32", "1234", 1),
    "HRD": (FunctionCode.READ_HOLDING_REGISTERS, "holding_register", "int32", "1234", 2),
    "DI": (FunctionCode.READ_DISCRETE_INPUTS, "discrete_input", "bool", "none", 1),
    "DA": (FunctionCode.READ_COILS, "coil", "bool", "none", 1),
}

_SYMBOL_RE = re.compile(r"^\s*sym-(?P<name>.+?)\s*=\s*(?P<type>[A-Za-z]+)\s*(?P<register>\d+)\s*,?\s*$")


def load_symbol_file(path: str | Path) -> SymbolPreview:
    """Parse an atvise Connect `.Symbol` file without interpreting connection data."""
    text = Path(path).read_text(encoding="utf-8-sig", errors="replace")
    rows: list[SymbolRow] = []
    ignored = 0
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped == "[]":
            continue
        match = _SYMBOL_RE.match(line)
        if not match:
            ignored += 1
            continue
        rows.append(SymbolRow(
            line_number=line_number,
            name=match.group("name").strip(),
            symbol_type=match.group("type").upper(),
            register=int(match.group("register")),
            raw=line,
        ))
    return SymbolPreview(str(path), rows, ignored)


def _target_requests(project: Project, device_name: str) -> list[Request]:
    for device in project.devices:
        if device.name == device_name:
            return device.requests
    for device in project.tcp_clients:
        if device.name == device_name:
            return device.requests
    raise ValueError(f"Target device {device_name!r} does not exist.")


def build_symbol_import_plan(
    project: Project,
    rows: list[SymbolRow],
    *,
    device_name: str,
    source_address_offset: int = 0,
    mapping_start: int = 1025,
) -> list[SymbolPlannedItem]:
    """Build a non-destructive plan using symbol addresses as physical device registers."""
    requests = _target_requests(project, device_name)
    existing_request_names = {r.name for r in requests}
    existing_mapping_names = {m.name for m in project.mappings}
    planned_requests: set[str] = set()
    planned_mappings: set[str] = set()
    shadow = replace(project, mappings=list(project.mappings))
    result: list[SymbolPlannedItem] = []

    for row in rows:
        spec = _SYMBOL_MAP.get(row.symbol_type)
        if spec is None:
            result.append(SymbolPlannedItem(row, None, None, f"Skip: unsupported symbol type {row.symbol_type}"))
            continue
        if not row.name:
            result.append(SymbolPlannedItem(row, None, None, "Skip: empty node name"))
            continue
        if row.name in existing_request_names or row.name in planned_requests:
            result.append(SymbolPlannedItem(row, None, None, f"Skip: duplicate request name {row.name}"))
            continue
        if row.name in existing_mapping_names or row.name in planned_mappings:
            result.append(SymbolPlannedItem(row, None, None, f"Skip: duplicate mapping name {row.name}"))
            continue

        function, register_type, data_type, byte_order, request_count = spec
        request = Request(
            name=row.name,
            function=function,
            register=row.register + source_address_offset,
            count=request_count,
            data_type=data_type,
            byte_order=byte_order,
            enabled=True,
        )
        width = register_value_width(data_type, register_type)
        server_register = first_free_register_range(shadow, register_type=register_type, width=width, default=mapping_start)
        mapping = ServerMapping(
            name=row.name,
            device=device_name,
            request=row.name,
            register=server_register,
            register_type=register_type,
            enabled=True,
            permissions="r",
            data_type=data_type,
            count=1,
        )
        shadow.mappings.append(mapping)
        planned_requests.add(row.name)
        planned_mappings.add(row.name)
        result.append(SymbolPlannedItem(row, request, mapping, "Ready"))
    return result


def repack_symbol_import_items(project: Project, items: list[SymbolPlannedItem], *, mapping_start: int = 1025) -> list[SymbolPlannedItem]:
    """Compact a selected subset into gap-free blocks per Modbus address space."""
    shadow = replace(project, mappings=list(project.mappings))
    packed: list[SymbolPlannedItem] = []
    for item in items:
        if item.request is None or item.mapping is None:
            packed.append(item)
            continue
        width = register_value_width(item.mapping.data_type, item.mapping.register_type)
        register = first_free_register_range(shadow, register_type=item.mapping.register_type, width=width, default=mapping_start)
        mapping = replace(item.mapping, register=register)
        shadow.mappings.append(mapping)
        packed.append(replace(item, mapping=mapping))
    return packed


def apply_symbol_import_plan(
    project: Project,
    items: list[SymbolPlannedItem],
    *,
    device_name: str,
    mapping_start: int = 1025,
) -> int:
    """Apply selected ready rows to an existing RTU or TCP target device."""
    requests = _target_requests(project, device_name)
    ready = [item for item in items if item.request is not None and item.mapping is not None]
    packed = repack_symbol_import_items(project, ready, mapping_start=mapping_start)
    requests.extend(item.request for item in packed if item.request is not None)
    project.mappings.extend(item.mapping for item in packed if item.mapping is not None)
    return len(packed)
