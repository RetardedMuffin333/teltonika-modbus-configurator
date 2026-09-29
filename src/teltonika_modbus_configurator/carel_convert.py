"""Convert parsed register-table rows into RutOS client requests and mappings."""

from __future__ import annotations

from dataclasses import dataclass, replace

from .carel_import import CarelImportRow
from .import_conflicts import (
    REPLACE_MATCHING,
    can_replace_name,
    replace_import_names,
    validate_conflict_policy,
)
from .models import FunctionCode, Project, Request, ServerMapping
from .read_batching import batch_read_items
from .register_allocator import first_free_register_range, register_value_width
from .scada_write import (
    CAREL_AUTO_WRITE_START,
    create_scada_write_target_from_definition,
)


@dataclass(slots=True)
class CarelPlannedItem:
    source: CarelImportRow
    request: Request | None
    mapping: ServerMapping | None
    status: str
    replace_existing: bool = False


# Carel cDesign names plus common generic-table aliases. Keeping the conversion
# normalized here lets different import profiles share the same planning code.
_TYPE_MAP = {
    "bool": ("bool", "none"), "boolean": ("bool", "none"),
    "usint": ("uint8", "none"), "uint8": ("uint8", "none"),
    "sint": ("int8", "none"), "int8": ("int8", "none"),
    "uint": ("uint16", "high_byte_first"), "uint16": ("uint16", "high_byte_first"),
    "int": ("int16", "high_byte_first"), "int16": ("int16", "high_byte_first"),
    "udint": ("uint32", "1234"), "uint32": ("uint32", "1234"),
    "dint": ("int32", "1234"), "int32": ("int32", "1234"),
    "real": ("float32", "1234"), "float": ("float32", "1234"), "float32": ("float32", "1234"),
}
_AREA_MAP = {
    "coil": (FunctionCode.READ_COILS, "coil"), "coils": (FunctionCode.READ_COILS, "coil"), "da": (FunctionCode.READ_COILS, "coil"),
    "discreteinput": (FunctionCode.READ_DISCRETE_INPUTS, "discrete_input"), "discreteinputs": (FunctionCode.READ_DISCRETE_INPUTS, "discrete_input"), "di": (FunctionCode.READ_DISCRETE_INPUTS, "discrete_input"),
    "holdingregister": (FunctionCode.READ_HOLDING_REGISTERS, "holding_register"), "holdingregisters": (FunctionCode.READ_HOLDING_REGISTERS, "holding_register"), "hr": (FunctionCode.READ_HOLDING_REGISTERS, "holding_register"),
    "inputregister": (FunctionCode.READ_INPUT_REGISTERS, "input_register"), "inputregisters": (FunctionCode.READ_INPUT_REGISTERS, "input_register"), "ir": (FunctionCode.READ_INPUT_REGISTERS, "input_register"),
}

def _key(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def is_carel_readwrite(row: CarelImportRow) -> bool:
    return _key(row.access) in {"rw", "readwrite", "readwrit"}


def _target_device(project: Project, device_name: str):
    return next(
        (device for device in (*project.devices, *project.tcp_clients) if device.name == device_name),
        None,
    )


def _device_name(*, device_name: str | None, tcp_device_name: str | None) -> str:
    """Resolve the target name while retaining the pre-v0.8 public keyword."""
    target = device_name or tcp_device_name
    if not target:
        raise ValueError("Select a Modbus RTU device or TCP client first.")
    if device_name and tcp_device_name and device_name != tcp_device_name:
        raise ValueError("Conflicting Carel import target device names.")
    return target


def build_carel_import_plan(
    project: Project,
    rows: list[CarelImportRow],
    *,
    device_name: str | None = None,
    tcp_device_name: str | None = None,
    add_one_to_index: bool = True,
    mapping_start: int = 1025,
    conflict_policy: str = "skip",
) -> list[CarelPlannedItem]:
    """Build a non-destructive import plan for an existing RTU or TCP client."""
    target_name = _device_name(device_name=device_name, tcp_device_name=tcp_device_name)
    validate_conflict_policy(conflict_policy)
    device = _target_device(project, target_name)
    if device is None:
        raise ValueError(f"Modbus RTU device or TCP client {target_name!r} does not exist.")

    existing_request_names = {r.name for r in device.requests}
    existing_mapping_names = {m.name for m in project.mappings}
    planned_request_names: set[str] = set(); planned_mapping_names: set[str] = set()
    shadow = Project(connections=project.connections, devices=project.devices, tcp_clients=project.tcp_clients, mappings=list(project.mappings), tcp_server=project.tcp_server, source_uci=project.source_uci)
    result: list[CarelPlannedItem] = []
    for row in rows:
        area = _AREA_MAP.get(_key(row.modbus_type)); dtype = _TYPE_MAP.get(_key(row.data_type))
        if area is None:
            result.append(CarelPlannedItem(row, None, None, f"Skip: unsupported Modbus type {row.modbus_type or '<empty>'}")); continue
        if dtype is None:
            result.append(CarelPlannedItem(row, None, None, f"Skip: unsupported datatype {row.data_type or '<empty>'}")); continue
        try:
            source_index = int(row.register)
        except (TypeError, ValueError):
            result.append(CarelPlannedItem(row, None, None, f"Skip: invalid register/index {row.register!r}")); continue
        if not row.name:
            result.append(CarelPlannedItem(row, None, None, "Skip: empty variable name")); continue
        if row.name in planned_request_names:
            result.append(CarelPlannedItem(row, None, None, f"Skip: duplicate request name {row.name}")); continue
        if row.name in planned_mapping_names:
            result.append(CarelPlannedItem(row, None, None, f"Skip: duplicate mapping name {row.name}")); continue
        existing_conflict = row.name in existing_request_names or row.name in existing_mapping_names
        replace_existing = existing_conflict and conflict_policy == REPLACE_MATCHING
        if existing_conflict and not replace_existing:
            result.append(CarelPlannedItem(row, None, None, f"Skip: existing request or mapping {row.name}")); continue
        if replace_existing and not can_replace_name(project, device_name=target_name, name=row.name):
            result.append(CarelPlannedItem(row, None, None, f"Skip: mapping name {row.name} belongs to another device")); continue

        function, register_type = area; data_type, byte_order = dtype
        request = Request(name=row.name, function=function, register=source_index + (1 if add_one_to_index else 0), count=1, data_type=data_type, byte_order=byte_order, enabled=True)
        width = register_value_width(data_type, register_type)
        server_register = first_free_register_range(shadow, register_type=register_type, width=width, default=mapping_start)
        mapping = ServerMapping(name=row.name, device=target_name, request=row.name, register=server_register, register_type=register_type, enabled=True, permissions="r", data_type=data_type, count=1)
        shadow.mappings.append(mapping); planned_request_names.add(row.name); planned_mapping_names.add(row.name)
        status = "Ready (replace existing)" if replace_existing else "Ready"
        result.append(CarelPlannedItem(row, request, mapping, status, replace_existing))
    return result


def repack_carel_import_items(project: Project, items: list[CarelPlannedItem], *, mapping_start: int = 1025) -> list[CarelPlannedItem]:
    """Re-pack a selected subset into compact TCP Server address blocks."""
    shadow = Project(connections=project.connections, devices=project.devices, tcp_clients=project.tcp_clients, mappings=list(project.mappings), tcp_server=project.tcp_server, source_uci=project.source_uci)
    packed: list[CarelPlannedItem] = []
    for item in items:
        if item.request is None or item.mapping is None:
            packed.append(item); continue
        mapping = item.mapping
        width = register_value_width(mapping.data_type, mapping.register_type)
        register = first_free_register_range(shadow, register_type=mapping.register_type, width=width, default=mapping_start)
        packed_mapping = replace(mapping, register=register)
        shadow.mappings.append(packed_mapping)
        packed.append(replace(item, mapping=packed_mapping))
    return packed


def batch_carel_read_items(
    device,
    items: list[CarelPlannedItem],
) -> tuple[list[Request], list[ServerMapping], list[CarelPlannedItem]]:
    """Replace typed one-value reads with bounded raw read blocks.

    Individual TCP Server tags keep their original names, datatypes and server
    addresses. ``source_offset`` selects the value inside the shared request via
    RutOS ``tag_start``.
    """
    return batch_read_items(device.requests, items)


def apply_carel_import_plan(
    project: Project,
    items: list[CarelPlannedItem],
    *,
    device_name: str | None = None,
    tcp_device_name: str | None = None,
    mapping_start: int = 1025,
    create_write_companions: bool = False,
    write_mapping_start: int = CAREL_AUTO_WRITE_START,
    batch_reads: bool = False,
) -> tuple[int, int]:
    """Apply selected rows and optionally create write companions for ReadWrite values.

    Returns ``(read_count, write_count)``. Only Coil and HoldingRegister ReadWrite
    rows are writable. FC selection is delegated to the hardware-verified SCADA
    helper: BOOL->FC05, 8/16-bit holding->FC06, 32-bit holding->FC16.
    """
    target_name = _device_name(device_name=device_name, tcp_device_name=tcp_device_name)
    device = _target_device(project, target_name)
    if device is None:
        raise ValueError(f"Modbus RTU device or TCP client {target_name!r} does not exist.")
    ready = [item for item in items if item.request is not None and item.mapping is not None]
    replace_import_names(
        project,
        device_name=target_name,
        names={item.source.name for item in ready if item.replace_existing},
    )
    packed = repack_carel_import_items(project, ready, mapping_start=mapping_start)
    semantic_items = list(packed)
    if batch_reads:
        block_requests, block_mappings, packed = batch_carel_read_items(device, packed)
        device.requests.extend(block_requests)
        project.mappings.extend(block_mappings)
    else:
        device.requests.extend(item.request for item in packed if item.request is not None)
    project.mappings.extend(item.mapping for item in packed if item.mapping is not None)

    write_count = 0
    if create_write_companions:
        final_mapping_by_name = {
            item.mapping.name: item.mapping for item in packed if item.mapping is not None
        }
        for item in semantic_items:
            if not is_carel_readwrite(item.source) or item.mapping is None or item.request is None:
                continue
            if item.mapping.register_type not in {"coil", "holding_register"}:
                continue
            create_scada_write_target_from_definition(
                project,
                device_name=target_name,
                read_request=item.request,
                feedback_mapping=final_mapping_by_name[item.mapping.name],
                write_block_start=write_mapping_start,
            )
            write_count += 1
    return len(packed), write_count
