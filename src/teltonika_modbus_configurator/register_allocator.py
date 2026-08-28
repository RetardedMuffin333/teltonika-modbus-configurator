"""Helpers for proposing free Modbus TCP Server register ranges."""

from __future__ import annotations

from .models import Project, ServerMapping


_TWO_REGISTER_TYPES = {"int32", "uint32", "float32"}


def register_value_width(data_type: str, register_type: str) -> int:
    """Return Modbus address width for one mapped value.

    32-bit values occupy two 16-bit holding/input registers. Bit areas and
    8/16-bit values occupy one address per value.
    """
    if register_type in {"holding_register", "input_register"} and data_type in _TWO_REGISTER_TYPES:
        return 2
    return 1


def mapping_width(mapping: ServerMapping) -> int:
    """Return total address width occupied by a TCP Server mapping."""
    return max(1, mapping.count) * register_value_width(mapping.data_type, mapping.register_type)


def first_free_register_range(
    project: Project,
    *,
    register_type: str,
    width: int = 1,
    default: int = 1025,
) -> int:
    """Return the first contiguous free range in one Modbus address space.

    Search begins at ``default`` and fills holes before later mappings. Disabled
    mappings are ignored because they do not occupy the live TCP Server address
    space. Width-aware mappings such as float32/int32/uint32 are respected.
    """
    width = max(1, width)
    candidate = max(1025, default)
    ranges = sorted(
        (m.register, m.register + mapping_width(m) - 1)
        for m in project.mappings
        if m.enabled and m.register_type == register_type
    )

    for start, end in ranges:
        if end < candidate:
            continue
        if candidate + width - 1 < start:
            return candidate
        candidate = max(candidate, end + 1)

    if candidate + width - 1 > 65536:
        raise ValueError(
            f"No free {register_type} range of width {width} remains in 1025..65536."
        )
    return candidate


def _source_block_width(project: Project, register_type: str, source_start: int) -> int:
    """Infer the source-device block width used by template cloning.

    ``allocate_template_mapping_layout`` passes the minimum register of the
    source device as ``default``. If a mapping starts there, use all mappings of
    that same device/address-space to determine how much contiguous room the
    cloned device will need.
    """
    anchors = [
        m for m in project.mappings
        if m.enabled and m.register_type == register_type and m.register == source_start
    ]
    widths = []
    for anchor in anchors:
        group = [
            m for m in project.mappings
            if m.enabled and m.register_type == register_type and m.device == anchor.device
        ]
        if group:
            widths.append(max((m.register - source_start) + mapping_width(m) for m in group))
    return max(widths, default=1)


def next_free_register(
    project: Project,
    *,
    register_type: str,
    request_name: str | None = None,
    default: int = 1000,
) -> int:
    """Return a suitable next register for a new mapping.

    Template cloning calls this without ``request_name``. In that mode the
    allocator uses first-fit placement and reserves the complete source-device
    block, allowing gaps below intentionally separated mappings to be reused.

    When ``request_name`` is supplied the historic request-group behaviour is
    preserved, which keeps manually added Temperature/Setpoint/etc. blocks
    familiar and backwards compatible.
    """
    if request_name is None:
        width = _source_block_width(project, register_type, default)
        return first_free_register_range(
            project, register_type=register_type, width=width, default=default
        )

    same_request = [
        m
        for m in project.mappings
        if m.register_type == register_type and m.request == request_name
    ]
    candidates = same_request or [
        m for m in project.mappings if m.register_type == register_type
    ]
    if not candidates:
        return default

    return max(m.register + mapping_width(m) for m in candidates)
