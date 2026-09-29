"""Shared conflict handling for register-table and Symbol imports."""

from __future__ import annotations

from .models import Project


SKIP_EXISTING = "skip"
REPLACE_MATCHING = "replace"
CONFLICT_POLICIES = {SKIP_EXISTING, REPLACE_MATCHING}


def validate_conflict_policy(policy: str) -> str:
    if policy not in CONFLICT_POLICIES:
        raise ValueError(f"Unknown import conflict policy {policy!r}.")
    return policy


def can_replace_name(project: Project, *, device_name: str, name: str) -> bool:
    """Return true when every existing collision belongs to the selected target."""
    foreign_mapping = any(
        mapping.name == name and mapping.device != device_name
        for mapping in project.mappings
    )
    return not foreign_mapping


def replace_import_names(project: Project, *, device_name: str, names: set[str]) -> None:
    """Remove matching imported values and their write companions safely.

    Symbol-only aliases may share a physical batch. A physical batch is removed
    only when its final alias is removed; otherwise the remaining aliases and
    their shared source request stay intact.
    """
    if not names:
        return
    source = next(
        (device for device in (*project.devices, *project.tcp_clients) if device.name == device_name),
        None,
    )
    if source is None:
        raise ValueError(f"Target device {device_name!r} does not exist.")

    replace_names = set(names) | {f"{name}_w" for name in names}
    candidate_batches = {
        mapping.request
        for mapping in project.mappings
        if mapping.device == device_name
        and mapping.name in replace_names
        and not mapping.deploy
    }
    project.mappings[:] = [
        mapping for mapping in project.mappings
        if not (mapping.device == device_name and mapping.name in replace_names)
    ]
    direct_requests = {
        request.name for request in source.requests if request.name in replace_names
    }

    orphan_batches = {
        request_name for request_name in candidate_batches
        if not any(
            mapping.device == device_name
            and mapping.request == request_name
            and not mapping.deploy
            for mapping in project.mappings
        )
    }
    if orphan_batches:
        project.mappings[:] = [
            mapping for mapping in project.mappings
            if not (
                mapping.device == device_name
                and mapping.request in orphan_batches
                and mapping.deploy
            )
        ]
    remove_requests = direct_requests | orphan_batches
    source.requests[:] = [
        request for request in source.requests if request.name not in remove_requests
    ]
