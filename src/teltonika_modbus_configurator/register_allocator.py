"""Helpers for proposing free Modbus TCP Server register ranges."""

from __future__ import annotations

from .models import Project, ServerMapping


def _mapping_count(project: Project, mapping: ServerMapping) -> int:
    device = next((d for d in project.devices if d.name == mapping.device), None)
    if device is None:
        return 1
    request = next((r for r in device.requests if r.name == mapping.request), None)
    return max(1, request.count) if request is not None else 1


def next_free_register(
    project: Project,
    *,
    register_type: str,
    request_name: str | None = None,
    default: int = 1000,
) -> int:
    """Return the next register after matching occupied ranges.

    When ``request_name`` is supplied, mappings with the same request name and
    register type are preferred. This preserves familiar grouped layouts such as
    Temperature, Setpoint and Command blocks when cloning an existing device.
    If no such mappings exist, all mappings of the requested TCP type are used.
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

    return max(m.register + _mapping_count(project, m) for m in candidates)
