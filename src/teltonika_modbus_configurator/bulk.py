"""Generic bulk device/request/mapping generation for the editor and CLI."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field

from .models import Device, FunctionCode, Project, Request, ServerMapping, permissions_for_function


@dataclass(slots=True)
class BulkRequestSpec:
    name: str
    function: FunctionCode
    register: int
    count: int = 1
    data_type: str = "int16"
    byte_order: str = "high_byte_first"
    enabled: bool = True
    values: str | None = None
    raw_data_type: str | None = None


@dataclass(slots=True)
class BulkMappingSpec:
    name_pattern: str
    request: str
    register_type: str
    start_register: int
    step: int = 1
    enabled: bool = True
    permissions: str = "r"
    data_type: str = "int16"
    count: int | None = None


@dataclass(slots=True)
class BulkSpec:
    connection: str
    name_pattern: str
    count: int
    start_index: int = 1
    slave_start: int = 1
    slave_step: int = 1
    slave_ids: list[int] | None = None
    period: int = 10
    timeout: int = 1
    enabled: bool = True
    requests: list[BulkRequestSpec] = field(default_factory=list)
    mappings: list[BulkMappingSpec] = field(default_factory=list)


@dataclass(slots=True)
class BulkResult:
    devices: list[Device]
    mappings: list[ServerMapping]


SUPPORTED_DATA_TYPES = {"int8", "uint8", "int16", "uint16", "int32", "uint32", "float32", "ascii", "hex", "bool", "pdu"}
BYTE_ORDERS_BY_TYPE = {
    "int8": {"none"}, "uint8": {"none"},
    "int16": {"high_byte_first", "low_byte_first"}, "uint16": {"high_byte_first", "low_byte_first"},
    "int32": {"1234", "2143", "3412", "4321"}, "uint32": {"1234", "2143", "3412", "4321"},
    "float32": {"1234", "2143", "3412", "4321"},
    "ascii": {"none"}, "hex": {"none"}, "bool": {"none"}, "pdu": {"none"},
}
READ_TYPES = {1: "coil", 2: "discrete_input", 3: "holding_register", 4: "input_register"}
WRITE_TYPES = {5: "coil", 6: "holding_register", 15: "coil", 16: "holding_register"}


def suggested_register_type(function: FunctionCode) -> str:
    """Return the natural Modbus TCP Server area for a source request."""
    return (READ_TYPES if function.is_read else WRITE_TYPES)[int(function)]


def _format(pattern: str, *, device: str, index: int, ordinal: int, request: str = "") -> str:
    try:
        return pattern.format(device=device, index=index, ordinal=ordinal, request=request)
    except (KeyError, IndexError, ValueError) as exc:
        raise ValueError(f"Invalid name pattern {pattern!r}: {exc}") from exc


def _mapping_width(mapping: ServerMapping) -> int:
    return max(1, mapping.count)


def _spec_mapping_width(mapping: BulkMappingSpec, request: BulkRequestSpec) -> int:
    return max(1, mapping.count if mapping.count is not None else request.count)


def _overlap(start_a: int, width_a: int, start_b: int, width_b: int) -> bool:
    return start_a <= start_b + width_b - 1 and start_b <= start_a + width_a - 1


def validate_bulk_spec(project: Project, spec: BulkSpec) -> list[str]:
    errors: list[str] = []
    if spec.count < 1: errors.append("Count must be at least 1.")
    if not spec.name_pattern: errors.append("Device name pattern is required.")
    if spec.connection not in {c.name for c in project.connections}: errors.append(f"Unknown connection: {spec.connection!r}.")
    if spec.period < 1: errors.append("Period must be at least 1.")
    if spec.timeout < 0: errors.append("Timeout cannot be negative.")
    if spec.slave_ids is not None:
        if len(spec.slave_ids) != spec.count: errors.append("Explicit Slave ID list length must equal count.")
        slave_ids = list(spec.slave_ids)
    else:
        slave_ids = [spec.slave_start + i * spec.slave_step for i in range(max(spec.count, 0))]
    for sid in slave_ids:
        if not 1 <= sid <= 247: errors.append(f"Slave ID {sid} is outside the Modbus range 1..247.")
    if len(set(slave_ids)) != len(slave_ids): errors.append("Generated Slave IDs contain duplicates.")

    request_names = [r.name for r in spec.requests]
    if len(set(request_names)) != len(request_names): errors.append("Request names must be unique within the template.")
    for r in spec.requests:
        if not r.name: errors.append("Request name is required.")
        if r.function.is_read and r.count < 1: errors.append(f"Request {r.name!r}: count must be at least 1.")
        if r.function.is_write and (r.values is None or not str(r.values).strip()): errors.append(f"Request {r.name!r}: write value(s) are required.")
        if r.register < 0 or r.register > 65535: errors.append(f"Request {r.name!r}: register must be in 0..65535.")
        if r.raw_data_type is None:
            if r.data_type not in SUPPORTED_DATA_TYPES:
                errors.append(f"Request {r.name!r}: unsupported data type {r.data_type!r}.")
            elif r.byte_order not in BYTE_ORDERS_BY_TYPE[r.data_type]:
                allowed = ", ".join(sorted(BYTE_ORDERS_BY_TYPE[r.data_type]))
                errors.append(f"Request {r.name!r}: byte order {r.byte_order!r} is invalid for {r.data_type}; use {allowed}.")

    request_by_name = {r.name: r for r in spec.requests}
    for m in spec.mappings:
        r = request_by_name.get(m.request)
        if r is None:
            errors.append(f"Mapping pattern {m.name_pattern!r} references unknown request {m.request!r}.")
            continue
        if m.start_register < 1025 or m.start_register > 65536: errors.append(f"Mapping {m.name_pattern!r}: start register must be in 1025..65536.")
        if m.step < 1: errors.append(f"Mapping {m.name_pattern!r}: step must be at least 1.")
        if m.register_type not in {"coil", "discrete_input", "holding_register", "input_register"}: errors.append(f"Mapping {m.name_pattern!r}: invalid TCP register type {m.register_type!r}.")
        if m.count is not None and m.count < 1: errors.append(f"Mapping {m.name_pattern!r}: count must be at least 1.")
        natural = suggested_register_type(r.function)
        if r.function.is_write and m.register_type != natural:
            errors.append(f"Mapping {m.name_pattern!r}: FC{int(r.function):02d} must use TCP type {natural!r}.")
        if r.function in {FunctionCode.READ_COILS, FunctionCode.READ_DISCRETE_INPUTS} and m.register_type != natural:
            errors.append(f"Mapping {m.name_pattern!r}: FC{int(r.function):02d} should use TCP type {natural!r}.")
    if errors: return errors

    existing_names = {d.name for d in project.devices}; existing_slave_pairs = {(d.connection, d.slave_id) for d in project.devices}
    existing_mapping_names = {m.name for m in project.mappings}; generated_names: set[str] = set(); generated_mapping_names: set[str] = set(); generated_ranges = []
    existing_ranges = [(m.register_type, m.register, _mapping_width(m), m.name) for m in project.mappings if m.enabled]
    for ordinal in range(spec.count):
        index = spec.start_index + ordinal; device_name = _format(spec.name_pattern, device="", index=index, ordinal=ordinal); sid = slave_ids[ordinal]
        if device_name in existing_names: errors.append(f"Device name {device_name!r} already exists.")
        if device_name in generated_names: errors.append(f"Device name pattern generates duplicate name {device_name!r}.")
        generated_names.add(device_name)
        if (spec.connection, sid) in existing_slave_pairs: errors.append(f"Slave ID {sid} is already used on connection {spec.connection!r}.")
        for m in spec.mappings:
            r = request_by_name[m.request]
            name = _format(m.name_pattern, device=device_name, index=index, ordinal=ordinal, request=m.request)
            register = m.start_register + ordinal * m.step; width = _spec_mapping_width(m, r)
            if name in existing_mapping_names: errors.append(f"TCP mapping name {name!r} already exists.")
            if name in generated_mapping_names: errors.append(f"TCP mapping pattern generates duplicate name {name!r}.")
            generated_mapping_names.add(name)
            if register + width - 1 > 65536: errors.append(f"TCP mapping {name!r} exceeds register 65536.")
            if m.enabled:
                for typ, start, ew, ename in existing_ranges:
                    if typ == m.register_type and _overlap(register, width, start, ew): errors.append(f"TCP {m.register_type} range {register}..{register + width - 1} for {name!r} overlaps existing mapping {ename!r}.")
                for typ, start, gw, gname in generated_ranges:
                    if typ == m.register_type and _overlap(register, width, start, gw): errors.append(f"TCP {m.register_type} range {register}..{register + width - 1} for {name!r} overlaps generated mapping {gname!r}.")
                generated_ranges.append((m.register_type, register, width, name))
    return errors


def generate_bulk(project: Project, spec: BulkSpec) -> BulkResult:
    errors = validate_bulk_spec(project, spec)
    if errors: raise ValueError("Bulk generation validation failed:\n- " + "\n- ".join(errors))
    slave_ids = list(spec.slave_ids) if spec.slave_ids is not None else [spec.slave_start + i * spec.slave_step for i in range(spec.count)]
    devices: list[Device] = []; mappings: list[ServerMapping] = []
    request_by_name = {r.name: r for r in spec.requests}
    for ordinal in range(spec.count):
        index = spec.start_index + ordinal; device_name = _format(spec.name_pattern, device="", index=index, ordinal=ordinal)
        device_requests = [Request(name=r.name, function=r.function, register=r.register, count=r.count, data_type=r.data_type, byte_order=r.byte_order, enabled=r.enabled, values=r.values, raw_data_type=r.raw_data_type) for r in spec.requests]
        devices.append(Device(name=device_name, slave_id=slave_ids[ordinal], connection=spec.connection, period=spec.period, timeout=spec.timeout, enabled=spec.enabled, requests=device_requests))
        for m in spec.mappings:
            r = request_by_name[m.request]; count = m.count if m.count is not None else max(1, r.count)
            mappings.append(ServerMapping(name=_format(m.name_pattern, device=device_name, index=index, ordinal=ordinal, request=m.request), device=device_name, request=m.request,
                                          register=m.start_register + ordinal * m.step, register_type=m.register_type, enabled=m.enabled,
                                          permissions=permissions_for_function(r.function), data_type=m.data_type, count=count))
    return BulkResult(devices=devices, mappings=mappings)


def apply_bulk(project: Project, spec: BulkSpec) -> BulkResult:
    result = generate_bulk(project, spec)
    project.devices.extend(deepcopy(result.devices)); project.mappings.extend(deepcopy(result.mappings))
    return result
