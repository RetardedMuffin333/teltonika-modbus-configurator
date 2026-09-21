"""Convert manually configured individual reads into physical batch reads."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from .models import Project, Request, ServerMapping
from .read_batching import batch_read_items
from .register_allocator import first_free_register_range


@dataclass(slots=True)
class _BatchItem:
    request: Request | None
    mapping: ServerMapping | None
    status: str = "Ready"


@dataclass(slots=True)
class ExistingBatchPlan:
    device_name: str
    original_request_names: list[str] = field(default_factory=list)
    original_mapping_indices: list[int] = field(default_factory=list)
    batch_requests: list[Request] = field(default_factory=list)
    block_mappings: list[ServerMapping] = field(default_factory=list)
    symbol_aliases: list[ServerMapping] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    @property
    def ready_count(self) -> int:
        return len(self.original_request_names)


def _source_device(project: Project, device_name: str):
    source = next((device for device in project.devices if device.name == device_name), None)
    if source is None:
        source = next((device for device in project.tcp_clients if device.name == device_name), None)
    if source is None:
        raise ValueError(f"Unknown RTU/TCP client {device_name!r}.")
    return source


def build_existing_batch_plan(
    project: Project, *, device_name: str, request_names: list[str], mapping_start: int = 1025
) -> ExistingBatchPlan:
    """Plan batching without changing the project.

    Only one-value read requests with exactly one deployed, symbol-exported TCP
    mapping are eligible. This avoids guessing how arrays or already-batched
    mappings should be represented as individual SCADA symbols.
    """
    source = _source_device(project, device_name)
    plan = ExistingBatchPlan(device_name=device_name)
    requested = list(dict.fromkeys(request_names))
    request_by_name = {request.name: request for request in source.requests}
    items: list[_BatchItem] = []

    for name in requested:
        request = request_by_name.get(name)
        if request is None:
            plan.skipped.append(f"{name}: request not found")
            continue
        if not request.function.is_read:
            plan.skipped.append(f"{name}: FC{int(request.function):02d} is not a read request")
            continue
        if not request.enabled:
            plan.skipped.append(f"{name}: request is disabled")
            continue
        candidates = [
            (index, mapping)
            for index, mapping in enumerate(project.mappings)
            if mapping.device == device_name and mapping.request == name and mapping.deploy
        ]
        if len(candidates) != 1:
            plan.skipped.append(f"{name}: expected exactly one deployed TCP mapping, found {len(candidates)}")
            continue
        mapping_index, mapping = candidates[0]
        if not mapping.export_symbol:
            plan.skipped.append(f"{name}: mapping is already a physical/non-symbol block")
            continue
        if mapping.count != 1:
            plan.skipped.append(f"{name}: mapping count {mapping.count} is not one semantic value")
            continue
        items.append(_BatchItem(request=request, mapping=replace(mapping, register=mapping_start)))
        plan.original_request_names.append(name)
        plan.original_mapping_indices.append(mapping_index)

    if not items:
        return plan

    batch_requests, block_mappings, converted = batch_read_items(source.requests, items)

    # Allocate one compact destination range per Modbus address space while
    # ignoring the individual mappings that this plan will replace.
    remaining = replace(
        project,
        mappings=[
            mapping for index, mapping in enumerate(project.mappings)
            if index not in set(plan.original_mapping_indices)
        ],
    )
    blocks_by_type: dict[str, list[ServerMapping]] = {}
    for mapping in block_mappings:
        blocks_by_type.setdefault(mapping.register_type, []).append(mapping)

    allocated_blocks: list[ServerMapping] = []
    block_by_request: dict[str, ServerMapping] = {}
    for register_type, blocks in blocks_by_type.items():
        total_width = sum(block.count for block in blocks)
        cursor = first_free_register_range(
            remaining, register_type=register_type, width=total_width, default=mapping_start
        )
        for block in blocks:
            allocated = replace(block, register=cursor)
            allocated_blocks.append(allocated)
            block_by_request[allocated.request] = allocated
            cursor += allocated.count

    aliases: list[ServerMapping] = []
    for item in converted:
        assert item.mapping is not None
        block = block_by_request[item.mapping.request]
        aliases.append(replace(item.mapping, register=block.register + item.mapping.source_offset))

    plan.batch_requests = batch_requests
    plan.block_mappings = allocated_blocks
    plan.symbol_aliases = aliases
    return plan


def apply_existing_batch_plan(project: Project, plan: ExistingBatchPlan) -> int:
    """Apply a previously built plan and return the number of batched values."""
    if not plan.original_request_names:
        return 0
    source = _source_device(project, plan.device_name)
    names = set(plan.original_request_names)
    mapping_indices = set(plan.original_mapping_indices)
    source.requests = [request for request in source.requests if request.name not in names]
    source.requests.extend(plan.batch_requests)
    project.mappings = [
        mapping for index, mapping in enumerate(project.mappings)
        if index not in mapping_indices
    ]
    project.mappings.extend(plan.block_mappings)
    project.mappings.extend(plan.symbol_aliases)
    return plan.ready_count
