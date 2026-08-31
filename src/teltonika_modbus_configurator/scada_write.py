"""Helpers for creating SCADA-driven Modbus write targets.

RutOS derives TCP Server tag permissions from the source Modbus Client request.
A polled FC03 request therefore exposes a read-only holding register, while a
(disabled) FC06 request exposes a write-only holding register. Keeping those
server mappings in separate address blocks avoids read block-merging failures in
clients such as atvise Connect.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import FunctionCode, Project, Request, ServerMapping
from .register_allocator import first_free_register_range, mapping_width


SCADA_WRITE_HOLDING_START = 1200


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
    """Allocate cloned mapping blocks while separating read and write access.

    Bulk templates can contain both read-only FC03 feedback mappings and
    write-only FC06 command mappings in the same holding-register address space.
    Grouping only by register type would make the gap between e.g. HR1031 and
    HR1200 part of one huge template block. Grouping by both register type and
    access keeps those areas compact and preserves the SCADA write separation.
    """
    result: dict[str, tuple[int, int]] = {}
    groups: dict[tuple[str, str], list[ServerMapping]] = {}
    for mapping in mappings:
        groups.setdefault((mapping.register_type, mapping.permissions), []).append(mapping)

    for (register_type, permissions), group in groups.items():
        source_min = min(m.register for m in group)
        block_width = max((m.register - source_min) + mapping_width(m) for m in group)
        floor = SCADA_WRITE_HOLDING_START if (
            register_type == "holding_register" and permissions == "w"
        ) else 1025
        base = first_free_register_range(
            project,
            register_type=register_type,
            width=block_width,
            default=max(floor, source_min),
        )
        for mapping in group:
            result[mapping.name] = (
                base + (mapping.register - source_min),
                block_width,
            )
    return result


def create_scada_write_target(
    project: Project,
    *,
    device_name: str,
    read_request_name: str,
    write_block_start: int = SCADA_WRITE_HOLDING_START,
) -> ScadaWriteTarget:
    """Create a disabled FC06 request and write-only TCP mapping.

    The first hardware-verified workflow targets one holding register at a time:
    an enabled FC03 request provides feedback, while an otherwise identical
    disabled FC06 request is used only when the TCP Server receives a SCADA
    write. The generated write mapping is allocated at/above register 1200 by
    default so it is not merged into the normal read block by atvise Connect.
    """
    source = _source_device(project, device_name)
    if source is None:
        raise ValueError(f"Unknown source device {device_name!r}.")

    read_request = next((r for r in source.requests if r.name == read_request_name), None)
    if read_request is None:
        raise ValueError(f"Unknown request {device_name}/{read_request_name}.")
    if read_request.function != FunctionCode.READ_HOLDING_REGISTERS:
        raise ValueError("SCADA write targets currently require an FC03 holding-register feedback request.")
    if read_request.count != 1:
        raise ValueError("SCADA write targets currently support one holding register per request.")

    feedback = [
        m for m in project.mappings
        if m.device == device_name and m.request == read_request_name and m.enabled
    ]
    if len(feedback) != 1:
        raise ValueError(
            "Create exactly one enabled TCP Server mapping for the FC03 feedback request first."
        )
    feedback_mapping = feedback[0]
    if feedback_mapping.register_type != "holding_register":
        raise ValueError("FC03 feedback must be mapped to a TCP holding register.")

    write_name = f"{read_request.name}_w"
    if any(r.name == write_name for r in source.requests):
        raise ValueError(f"Request {write_name!r} already exists on {device_name}.")
    if any(m.name == write_name for m in project.mappings):
        raise ValueError(f"TCP mapping {write_name!r} already exists.")

    width = mapping_width(feedback_mapping)
    tcp_register = first_free_register_range(
        project,
        register_type="holding_register",
        width=width,
        default=max(SCADA_WRITE_HOLDING_START, int(write_block_start)),
    )

    write_request = Request(
        name=write_name,
        function=FunctionCode.WRITE_SINGLE_HOLDING_REGISTER,
        register=read_request.register,
        count=1,
        data_type=read_request.data_type,
        byte_order=read_request.byte_order,
        enabled=False,
        # RutOS requires a configured value for FC06. Because this request is
        # disabled, the placeholder is not periodically written; incoming TCP
        # Server writes supply the actual value at runtime.
        values="0",
    )
    write_mapping = ServerMapping(
        name=write_name,
        device=device_name,
        request=write_name,
        register=tcp_register,
        register_type="holding_register",
        enabled=True,
        permissions="w",
        data_type=feedback_mapping.data_type,
        count=feedback_mapping.count,
    )

    source.requests.append(write_request)
    project.mappings.append(write_mapping)
    return ScadaWriteTarget(write_request, write_mapping, feedback_mapping)
