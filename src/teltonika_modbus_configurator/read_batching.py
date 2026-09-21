"""Shared read-request batching for register-table and Symbol imports."""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from .models import FunctionCode, Request, ServerMapping
from .register_allocator import register_value_width


BATCH_LIMIT = {
    FunctionCode.READ_HOLDING_REGISTERS: 100,
    FunctionCode.READ_INPUT_REGISTERS: 100,
    FunctionCode.READ_COILS: 1000,
    FunctionCode.READ_DISCRETE_INPUTS: 1000,
}


def _unique_request_name(existing: Iterable[Request], base: str, reserved: set[str]) -> str:
    used = {request.name for request in existing} | reserved
    if base not in used:
        reserved.add(base)
        return base
    ordinal = 2
    while f"{base}_{ordinal}" in used:
        ordinal += 1
    name = f"{base}_{ordinal}"
    reserved.add(name)
    return name


def batch_read_items(
    existing_requests: Iterable[Request],
    items: list,
) -> tuple[list[Request], list[ServerMapping], list]:
    """Replace compatible one-value reads with bounded raw read blocks.

    Items may come from any import format as long as they expose ``request``,
    ``mapping`` and ``status`` dataclass fields. Individual semantic mappings
    remain as symbol-only aliases while one physical mapping serves each block.
    """
    existing_requests = list(existing_requests)
    groups: dict[FunctionCode, list] = {}
    for item in items:
        if item.request is None or item.mapping is None or not item.request.function.is_read:
            continue
        groups.setdefault(item.request.function, []).append(item)

    requests: list[Request] = []
    block_mappings: list[ServerMapping] = []
    converted: list = []
    reserved: set[str] = set()
    for function, group in groups.items():
        register_type = group[0].mapping.register_type
        destination_cursor = min(item.mapping.register for item in group)
        limit = BATCH_LIMIT[function]
        ordered = sorted(group, key=lambda item: item.request.register)
        blocks: list[list] = []
        current: list = []
        block_start = 0
        for item in ordered:
            width = register_value_width(item.request.data_type, register_type)
            item_start = item.request.register
            item_end = item_start + width - 1
            if current and item_end - block_start + 1 > limit:
                blocks.append(current)
                current = []
            if not current:
                block_start = item_start
            current.append(item)
        if current:
            blocks.append(current)

        for block in blocks:
            start = min(item.request.register for item in block)
            end = max(
                item.request.register + register_value_width(item.request.data_type, register_type) - 1
                for item in block
            )
            raw_type = "bool" if register_type in {"coil", "discrete_input"} else "uint16"
            raw_order = "none" if raw_type == "bool" else "high_byte_first"
            name = _unique_request_name(existing_requests, f"Batch_FC{int(function):02d}_{start}_{end}", reserved)
            request = Request(
                name=name,
                function=function,
                register=start,
                count=end - start + 1,
                data_type=raw_type,
                byte_order=raw_order,
                enabled=True,
            )
            requests.append(request)
            block_mappings.append(ServerMapping(
                name=name,
                device=group[0].mapping.device,
                request=name,
                register=destination_cursor,
                register_type=register_type,
                enabled=True,
                permissions="r",
                data_type=raw_type,
                count=request.count,
                source_offset=0,
                export_symbol=False,
            ))
            for item in block:
                value_width = register_value_width(item.request.data_type, register_type)
                source_offset = item.request.register - start
                mapping = replace(
                    item.mapping,
                    request=name,
                    register=destination_cursor + source_offset,
                    source_offset=source_offset,
                    data_type=raw_type,
                    count=value_width,
                    symbol_data_type=item.mapping.data_type,
                    deploy=False,
                    export_symbol=True,
                )
                converted.append(replace(item, request=request, mapping=mapping, status="Ready (batched)"))
            destination_cursor += request.count
    return requests, block_mappings, converted
