"""Convert parsed Carel cDesign rows into RutOS TCP-client requests and mappings."""

from __future__ import annotations

from dataclasses import dataclass

from .carel_import import CarelImportRow
from .models import FunctionCode, Project, Request, ServerMapping
from .register_allocator import first_free_register_range, register_value_width


@dataclass(slots=True)
class CarelPlannedItem:
    source: CarelImportRow
    request: Request | None
    mapping: ServerMapping | None
    status: str


_TYPE_MAP = {
    "bool": ("bool", "none"),
    "usint": ("uint8", "none"),
    "sint": ("int8", "none"),
    "uint": ("uint16", "high_byte_first"),
    "int": ("int16", "high_byte_first"),
    "udint": ("uint32", "1234"),
    "dint": ("int32", "1234"),
    "real": ("float32", "1234"),
    "float": ("float32", "1234"),
}

_AREA_MAP = {
    "coil": (FunctionCode.READ_COILS, "coil"),
    "discreteinput": (FunctionCode.READ_DISCRETE_INPUTS, "discrete_input"),
    "holdingregister": (FunctionCode.READ_HOLDING_REGISTERS, "holding_register"),
    "inputregister": (FunctionCode.READ_INPUT_REGISTERS, "input_register"),
}


def _key(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def build_carel_import_plan(
    project: Project,
    rows: list[CarelImportRow],
    *,
    tcp_device_name: str,
    add_one_to_index: bool = True,
    mapping_start: int = 1025,
) -> list[CarelPlannedItem]:
    """Build a non-destructive import plan for one existing Modbus TCP client."""
    device = next((d for d in project.tcp_clients if d.name == tcp_device_name), None)
    if device is None:
        raise ValueError(f"Modbus TCP client {tcp_device_name!r} does not exist.")

    existing_request_names = {r.name for r in device.requests}
    existing_mapping_names = {m.name for m in project.mappings}
    planned_request_names: set[str] = set()
    planned_mapping_names: set[str] = set()

    # Track temporary mappings so first-fit allocation also sees earlier planned rows.
    shadow = Project(
        connections=project.connections,
        devices=project.devices,
        tcp_clients=project.tcp_clients,
        mappings=list(project.mappings),
        tcp_server=project.tcp_server,
        source_uci=project.source_uci,
    )

    result: list[CarelPlannedItem] = []
    for row in rows:
        area = _AREA_MAP.get(_key(row.modbus_type))
        dtype = _TYPE_MAP.get(_key(row.data_type))
        if area is None:
            result.append(CarelPlannedItem(row, None, None, f"Skip: unsupported Modbus type {row.modbus_type or '<empty>'}"))
            continue
        if dtype is None:
            result.append(CarelPlannedItem(row, None, None, f"Skip: unsupported Carel datatype {row.data_type or '<empty>'}"))
            continue
        try:
            carel_index = int(row.register)
        except (TypeError, ValueError):
            result.append(CarelPlannedItem(row, None, None, f"Skip: invalid Carel index {row.register!r}"))
            continue
        if not row.name:
            result.append(CarelPlannedItem(row, None, None, "Skip: empty variable name"))
            continue
        if row.name in existing_request_names or row.name in planned_request_names:
            result.append(CarelPlannedItem(row, None, None, f"Skip: duplicate request name {row.name}"))
            continue
        if row.name in existing_mapping_names or row.name in planned_mapping_names:
            result.append(CarelPlannedItem(row, None, None, f"Skip: duplicate mapping name {row.name}"))
            continue

        function, register_type = area
        data_type, byte_order = dtype
        rut_register = carel_index + (1 if add_one_to_index else 0)
        request = Request(
            name=row.name,
            function=function,
            register=rut_register,
            count=1,
            data_type=data_type,
            byte_order=byte_order,
            enabled=True,
        )
        width = register_value_width(data_type, register_type)
        server_register = first_free_register_range(
            shadow,
            register_type=register_type,
            width=width,
            default=mapping_start,
        )
        mapping = ServerMapping(
            name=row.name,
            device=tcp_device_name,
            request=row.name,
            register=server_register,
            register_type=register_type,
            enabled=True,
            permissions="r",
            data_type=data_type,
            count=1,
        )
        shadow.mappings.append(mapping)
        planned_request_names.add(row.name)
        planned_mapping_names.add(row.name)
        result.append(CarelPlannedItem(row, request, mapping, "Ready"))
    return result


def apply_carel_import_plan(project: Project, items: list[CarelPlannedItem], *, tcp_device_name: str) -> int:
    """Append all ready planned requests/mappings to the project and return count."""
    device = next((d for d in project.tcp_clients if d.name == tcp_device_name), None)
    if device is None:
        raise ValueError(f"Modbus TCP client {tcp_device_name!r} does not exist.")
    ready = [item for item in items if item.request is not None and item.mapping is not None]
    device.requests.extend(item.request for item in ready if item.request is not None)
    project.mappings.extend(item.mapping for item in ready if item.mapping is not None)
    return len(ready)
