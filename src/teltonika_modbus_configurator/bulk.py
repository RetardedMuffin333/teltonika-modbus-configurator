"""Generic bulk device/request/mapping generation for the editor and CLI."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field

from .models import Device, FunctionCode, Project, Request, ServerMapping


@dataclass(slots=True)
class BulkRequestSpec:
    name: str
    function: FunctionCode
    register: int
    count: int = 1
    data_type: str = "int16"
    byte_order: str = "high_byte_first"
    enabled: bool = True


@dataclass(slots=True)
class BulkMappingSpec:
    name_pattern: str
    request: str
    register_type: str
    start_register: int
    step: int = 1
    enabled: bool = True


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


def _format(pattern: str, *, device: str, index: int, ordinal: int, request: str = "") -> str:
    try:
        return pattern.format(device=device, index=index, ordinal=ordinal, request=request)
    except (KeyError, IndexError, ValueError) as exc:
        raise ValueError(f"Invalid name pattern {pattern!r}: {exc}") from exc


def _mapping_width(project: Project, mapping: ServerMapping) -> int:
    """Return the number of TCP addresses occupied by a mapping's source request."""
    for device in project.devices:
        if device.name != mapping.device:
            continue
        for request in device.requests:
            if request.name == mapping.request:
                return max(1, request.count)
    return 1


def _overlap(start_a: int, width_a: int, start_b: int, width_b: int) -> bool:
    return start_a <= start_b + width_b - 1 and start_b <= start_a + width_a - 1


def validate_bulk_spec(project: Project, spec: BulkSpec) -> list[str]:
    errors: list[str] = []

    if spec.count < 1:
        errors.append("Count must be at least 1.")
    if not spec.name_pattern:
        errors.append("Device name pattern is required.")
    if spec.connection not in {c.name for c in project.connections}:
        errors.append(f"Unknown connection: {spec.connection!r}.")
    if spec.period < 1:
        errors.append("Period must be at least 1.")
    if spec.timeout < 0:
        errors.append("Timeout cannot be negative.")

    if spec.slave_ids is not None:
        if len(spec.slave_ids) != spec.count:
            errors.append("Explicit Slave ID list length must equal count.")
        slave_ids = list(spec.slave_ids)
    else:
        slave_ids = [spec.slave_start + i * spec.slave_step for i in range(max(spec.count, 0))]

    for sid in slave_ids:
        if not 1 <= sid <= 247:
            errors.append(f"Slave ID {sid} is outside the Modbus range 1..247.")

    if len(set(slave_ids)) != len(slave_ids):
        errors.append("Generated Slave IDs contain duplicates.")

    request_names = [r.name for r in spec.requests]
    if len(set(request_names)) != len(request_names):
        errors.append("Request names must be unique within the template.")
    for request in spec.requests:
        if request.count < 1:
            errors.append(f"Request {request.name!r}: count must be at least 1.")
        if request.register < 0:
            errors.append(f"Request {request.name!r}: register cannot be negative.")

    request_by_name = {r.name: r for r in spec.requests}
    for mapping in spec.mappings:
        if mapping.request not in request_by_name:
            errors.append(
                f"Mapping pattern {mapping.name_pattern!r} references unknown request {mapping.request!r}."
            )
        if mapping.start_register < 0:
            errors.append(f"Mapping {mapping.name_pattern!r}: start register cannot be negative.")
        if mapping.step < 1:
            errors.append(f"Mapping {mapping.name_pattern!r}: step must be at least 1.")
        if mapping.register_type not in {"coil", "discrete_input", "holding_register", "input_register"}:
            errors.append(f"Mapping {mapping.name_pattern!r}: invalid TCP register type {mapping.register_type!r}.")

    if errors:
        return errors

    existing_names = {d.name for d in project.devices}
    existing_slave_pairs = {(d.connection, d.slave_id) for d in project.devices}
    existing_mapping_names = {m.name for m in project.mappings}

    generated_names: set[str] = set()
    generated_mapping_names: set[str] = set()
    generated_ranges: list[tuple[str, int, int, str]] = []

    existing_ranges = [
        (m.register_type, m.register, _mapping_width(project, m), m.name)
        for m in project.mappings
        if m.enabled
    ]

    for ordinal in range(spec.count):
        index = spec.start_index + ordinal
        device_name = _format(spec.name_pattern, device="", index=index, ordinal=ordinal)
        sid = slave_ids[ordinal]

        if device_name in existing_names:
            errors.append(f"Device name {device_name!r} already exists.")
        if device_name in generated_names:
            errors.append(f"Device name pattern generates duplicate name {device_name!r}.")
        generated_names.add(device_name)

        if (spec.connection, sid) in existing_slave_pairs:
            errors.append(f"Slave ID {sid} is already used on connection {spec.connection!r}.")

        for mapping in spec.mappings:
            request = request_by_name[mapping.request]
            name = _format(
                mapping.name_pattern,
                device=device_name,
                index=index,
                ordinal=ordinal,
                request=mapping.request,
            )
            register = mapping.start_register + ordinal * mapping.step
            width = max(1, request.count)

            if name in existing_mapping_names:
                errors.append(f"TCP mapping name {name!r} already exists.")
            if name in generated_mapping_names:
                errors.append(f"TCP mapping pattern generates duplicate name {name!r}.")
            generated_mapping_names.add(name)

            if mapping.enabled:
                for typ, start, existing_width, existing_name in existing_ranges:
                    if typ == mapping.register_type and _overlap(register, width, start, existing_width):
                        errors.append(
                            f"TCP {mapping.register_type} range {register}..{register + width - 1} "
                            f"for {name!r} overlaps existing mapping {existing_name!r}."
                        )
                for typ, start, generated_width, generated_name in generated_ranges:
                    if typ == mapping.register_type and _overlap(register, width, start, generated_width):
                        errors.append(
                            f"TCP {mapping.register_type} range {register}..{register + width - 1} "
                            f"for {name!r} overlaps generated mapping {generated_name!r}."
                        )
                generated_ranges.append((mapping.register_type, register, width, name))

    return errors


def generate_bulk(project: Project, spec: BulkSpec) -> BulkResult:
    errors = validate_bulk_spec(project, spec)
    if errors:
        raise ValueError("Bulk generation validation failed:\n- " + "\n- ".join(errors))

    if spec.slave_ids is not None:
        slave_ids = list(spec.slave_ids)
    else:
        slave_ids = [spec.slave_start + i * spec.slave_step for i in range(spec.count)]

    devices: list[Device] = []
    mappings: list[ServerMapping] = []

    for ordinal in range(spec.count):
        index = spec.start_index + ordinal
        device_name = _format(spec.name_pattern, device="", index=index, ordinal=ordinal)
        device_requests = [
            Request(
                name=r.name,
                function=r.function,
                register=r.register,
                count=r.count,
                data_type=r.data_type,
                byte_order=r.byte_order,
                enabled=r.enabled,
            )
            for r in spec.requests
        ]
        devices.append(
            Device(
                name=device_name,
                slave_id=slave_ids[ordinal],
                connection=spec.connection,
                period=spec.period,
                timeout=spec.timeout,
                enabled=spec.enabled,
                requests=device_requests,
            )
        )

        for mapping in spec.mappings:
            mappings.append(
                ServerMapping(
                    name=_format(
                        mapping.name_pattern,
                        device=device_name,
                        index=index,
                        ordinal=ordinal,
                        request=mapping.request,
                    ),
                    device=device_name,
                    request=mapping.request,
                    register=mapping.start_register + ordinal * mapping.step,
                    register_type=mapping.register_type,
                    enabled=mapping.enabled,
                )
            )

    return BulkResult(devices=devices, mappings=mappings)


def apply_bulk(project: Project, spec: BulkSpec) -> BulkResult:
    """Validate, generate, and append a batch atomically to a project."""
    result = generate_bulk(project, spec)
    project.devices.extend(deepcopy(result.devices))
    project.mappings.extend(deepcopy(result.mappings))
    return result
