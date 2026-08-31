"""Helpers for creating SCADA-driven Modbus write targets.

RutOS derives TCP Server tag permissions from the source Modbus Client request.
Polled read requests expose read-only server values, while disabled write
requests expose write-only values. Keeping those mappings in separate address
blocks avoids block-read failures in clients such as atvise Connect.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import FunctionCode, Project, Request, ServerMapping
from .register_allocator import first_free_register_range, mapping_width


SCADA_WRITE_HOLDING_START = 1200
SCADA_WRITE_COIL_START = 1200


@dataclass(slots=True)
class ScadaWriteTarget:
    request: Request
    mapping: ServerMapping
    feedback_mapping: ServerMapping


def _source_device(project: Project, device_name: str):
    return next(
        (d for d in [*project.devices, *project.tcp_clients] if d.name == device_name),
        None,
    )


def allocate_scada_template_mapping_layout(
    project: Project,
    mappings: list[ServerMapping],
) -> dict[str, tuple[int, int]]:
    """Allocate cloned mapping blocks while separating read and write access."""
    result: dict[str, tuple[int, int]] = {}
    groups: dict[tuple[str, str], list[ServerMapping]] = {}
    for mapping in mappings:
        groups.setdefault((mapping.register_type, mapping.permissions), []).append(mapping)

    for (register_type, permissions), group in groups.items():
        source_min = min(m.register for m in group)
        block_width = max((m.register - source_min) + mapping_width(m) for m in group)
        floor = 1025
        if permissions == "w" and register_type == "holding_register":
            floor = SCADA_WRITE_HOLDING_START
        elif permissions == "w" and register_type == "coil":
            floor = SCADA_WRITE_COIL_START
        base = first_free_register_range(
            project,
            register_type=register_type,
            width=block_width,
            default=max(floor, source_min),
        )
        for mapping in group:
            result[mapping.name] = (base + (mapping.register - source_min), block_width)
    return result


def create_scada_write_target(
    project: Project,
    *,
    device_name: str,
    read_request_name: str,
    write_block_start: int | None = None,
) -> ScadaWriteTarget:
    """Create a disabled write companion and write-only TCP mapping.

    Hardware-verified FC03 feedback uses a disabled FC06 companion. v0.4 also
    supports writable Carel coils: FC01 feedback uses a disabled FC05 companion.
    In both cases the command mapping is allocated in a separate 1200+ block so
    atvise Connect cannot merge write-only values into its normal read block.
    """
    source = _source_device(project, device_name)
    if source is None:
        raise ValueError(f"Unknown source device {device_name!r}.")

    read_request = next((r for r in source.requests if r.name == read_request_name), None)
    if read_request is None:
        raise ValueError(f"Unknown request {device_name}/{read_request_name}.")
    if read_request.count != 1:
        raise ValueError("SCADA write targets currently support one value per request.")

    if read_request.function == FunctionCode.READ_HOLDING_REGISTERS:
        write_function = FunctionCode.WRITE_SINGLE_HOLDING_REGISTER
        required_mapping_type = "holding_register"
        default_write_start = SCADA_WRITE_HOLDING_START
    elif read_request.function == FunctionCode.READ_COILS:
        write_function = FunctionCode.WRITE_SINGLE_COIL
        required_mapping_type = "coil"
        default_write_start = SCADA_WRITE_COIL_START
    else:
        raise ValueError("SCADA write targets require FC03 holding-register or FC01 coil feedback.")

    feedback = [
        m for m in project.mappings
        if m.device == device_name and m.request == read_request_name and m.enabled
    ]
    if len(feedback) != 1:
        raise ValueError("Create exactly one enabled TCP Server mapping for the feedback request first.")
    feedback_mapping = feedback[0]
    if feedback_mapping.register_type != required_mapping_type:
        raise ValueError(f"Feedback must be mapped to TCP {required_mapping_type}.")

    write_name = f"{read_request.name}_w"
    if any(r.name == write_name for r in source.requests):
        raise ValueError(f"Request {write_name!r} already exists on {device_name}.")
    if any(m.name == write_name for m in project.mappings):
        raise ValueError(f"TCP mapping {write_name!r} already exists.")

    width = mapping_width(feedback_mapping)
    floor = default_write_start if write_block_start is None else int(write_block_start)
    tcp_register = first_free_register_range(
        project,
        register_type=required_mapping_type,
        width=width,
        default=max(default_write_start, floor),
    )

    write_request = Request(
        name=write_name,
        function=write_function,
        register=read_request.register,
        count=1,
        data_type=read_request.data_type,
        byte_order=read_request.byte_order,
        enabled=False,
        values="0",
    )
    write_mapping = ServerMapping(
        name=write_name,
        device=device_name,
        request=write_name,
        register=tcp_register,
        register_type=required_mapping_type,
        enabled=True,
        permissions="w",
        data_type=feedback_mapping.data_type,
        count=feedback_mapping.count,
    )

    source.requests.append(write_request)
    project.mappings.append(write_mapping)
    return ScadaWriteTarget(write_request, write_mapping, feedback_mapping)
