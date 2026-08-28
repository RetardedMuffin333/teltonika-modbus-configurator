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


def next_free_register(
    project: Project,
    *,
    register_type: str,
    request_name: str | None = None,
    default: int = 1000,
) -> int:
    """Return the next register after matching occupied ranges.

    When ``request_name`` is supplied, mappings with the same request name and
    register type are preferred. If none exist, all mappings of the requested
    TCP type are used. Mapping datatype width is respected, so float32/int32/
    uint32 mappings reserve two 16-bit Modbus registers per value.
    """

    same_request = [
        m
        for m in project.mappings
        if m.register_type == register_type and request_name and m.request == request_name
    ]
    candidates = same_request or [
        m for m in project.mappings if m.register_type == register_type
    ]
    if not candidates:
        return default

    return max(m.register + mapping_width(m) for m in candidates)
