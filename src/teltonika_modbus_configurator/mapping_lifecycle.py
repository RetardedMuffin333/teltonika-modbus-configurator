"""Keep physical TCP mappings and symbol-only aliases consistent."""

from __future__ import annotations

from .models import Project, ServerMapping


def deployed_mappings_for_request(
    project: Project, *, device_name: str, request_name: str
) -> list[ServerMapping]:
    """Return physical RutOS mappings that still require a source request."""
    return [
        mapping
        for mapping in project.mappings
        if mapping.deploy
        and mapping.device == device_name
        and mapping.request == request_name
    ]


def deployed_mappings_for_device(
    project: Project, *, device_name: str
) -> list[ServerMapping]:
    """Return physical RutOS mappings that still require a source device."""
    return [
        mapping
        for mapping in project.mappings
        if mapping.deploy and mapping.device == device_name
    ]


def remove_symbol_aliases_for_requests(
    project: Project, *, device_name: str, request_names: set[str]
) -> int:
    """Remove non-deployed aliases after their source requests are removed."""
    before = len(project.mappings)
    project.mappings[:] = [
        mapping
        for mapping in project.mappings
        if not (
            not mapping.deploy
            and mapping.device == device_name
            and mapping.request in request_names
        )
    ]
    return before - len(project.mappings)


def remove_symbol_aliases_for_device(project: Project, *, device_name: str) -> int:
    """Remove non-deployed aliases after their source device is removed."""
    before = len(project.mappings)
    project.mappings[:] = [
        mapping
        for mapping in project.mappings
        if mapping.deploy or mapping.device != device_name
    ]
    return before - len(project.mappings)


def remove_server_mappings(project: Project, indices: list[int]) -> int:
    """Remove selected mappings and aliases owned by selected physical blocks."""
    selected = {
        index for index in indices if 0 <= index < len(project.mappings)
    }
    block_keys = {
        (mapping.device, mapping.request)
        for index, mapping in enumerate(project.mappings)
        if index in selected and mapping.deploy
    }
    before = len(project.mappings)
    project.mappings[:] = [
        mapping
        for index, mapping in enumerate(project.mappings)
        if index not in selected
        and not (
            not mapping.deploy
            and (mapping.device, mapping.request) in block_keys
        )
    ]
    return before - len(project.mappings)
