"""Build physical FC15/FC16 write blocks with individual SCADA aliases."""

from __future__ import annotations

from dataclasses import replace

from .models import FunctionCode, Project, Request, ServerMapping
from .read_batching import BATCH_LIMIT
from .register_allocator import first_free_register_range, register_value_width
from .scada_write import WRITE_MAPPING_START


def _unique_name(existing: list[Request], base: str, reserved: set[str]) -> str:
    used = {request.name for request in existing} | reserved
    if base not in used:
        reserved.add(base)
        return base
    number = 2
    while f"{base}_{number}" in used:
        number += 1
    result = f"{base}_{number}"
    reserved.add(result)
    return result


def batch_write_items(
    project: Project,
    *,
    device_name: str,
    items: list,
    mapping_start: int = WRITE_MAPPING_START,
) -> tuple[list[Request], list[ServerMapping], list[ServerMapping]]:
    """Convert writable semantic definitions into bounded raw write blocks."""
    source = next(
        (device for device in (*project.devices, *project.tcp_clients) if device.name == device_name),
        None,
    )
    if source is None:
        raise ValueError(f"Target device {device_name!r} does not exist.")

    groups: dict[str, list] = {"coil": [], "holding_register": []}
    for item in items:
        if item.request is not None and item.mapping is not None and item.mapping.register_type in groups:
            groups[item.mapping.register_type].append(item)

    requests: list[Request] = []
    blocks: list[ServerMapping] = []
    aliases: list[ServerMapping] = []
    reserved: set[str] = set()
    shadow = replace(project, mappings=list(project.mappings))
    for register_type, group in groups.items():
        if not group:
            continue
        ordered = sorted(group, key=lambda item: item.request.register)
        limit = BATCH_LIMIT[
            FunctionCode.READ_COILS if register_type == "coil"
            else FunctionCode.READ_HOLDING_REGISTERS
        ]
        partitions: list[list] = []
        current: list = []
        start = 0
        for item in ordered:
            width = register_value_width(item.request.data_type, register_type)
            end = item.request.register + width - 1
            if current and end - start + 1 > limit:
                partitions.append(current)
                current = []
            if not current:
                start = item.request.register
            current.append(item)
        if current:
            partitions.append(current)

        area = "DA" if register_type == "coil" else "HR"
        for partition in partitions:
            source_start = min(item.request.register for item in partition)
            source_end = max(
                item.request.register + register_value_width(item.request.data_type, register_type) - 1
                for item in partition
            )
            width = source_end - source_start + 1
            name = _unique_name(
                source.requests,
                f"Batch_{area}_WRITE_{source_start}_{source_end}",
                reserved,
            )
            raw_type = "bool" if register_type == "coil" else "uint16"
            request = Request(
                name=name,
                function=(
                    FunctionCode.WRITE_MULTIPLE_COILS
                    if register_type == "coil"
                    else FunctionCode.WRITE_MULTIPLE_HOLDING_REGISTERS
                ),
                register=source_start,
                count=width,
                data_type=raw_type,
                byte_order="none" if raw_type == "bool" else "high_byte_first",
                enabled=False,
                values=" ".join("0" for _ in range(width)),
            )
            destination = first_free_register_range(
                shadow,
                register_type=register_type,
                width=width,
                default=max(WRITE_MAPPING_START, mapping_start),
            )
            block = ServerMapping(
                name=name,
                device=device_name,
                request=name,
                register=destination,
                register_type=register_type,
                enabled=True,
                permissions="w",
                data_type=raw_type,
                count=width,
                export_symbol=False,
            )
            requests.append(request)
            blocks.append(block)
            shadow.mappings.append(block)
            for item in partition:
                value_width = register_value_width(item.request.data_type, register_type)
                offset = item.request.register - source_start
                aliases.append(ServerMapping(
                    name=f"{item.source.name}_w",
                    device=device_name,
                    request=name,
                    register=destination + offset,
                    register_type=register_type,
                    enabled=True,
                    permissions="w",
                    data_type=raw_type,
                    count=value_width,
                    source_offset=offset,
                    symbol_data_type=item.request.data_type,
                    deploy=False,
                    export_symbol=True,
                ))
    return requests, blocks, aliases
