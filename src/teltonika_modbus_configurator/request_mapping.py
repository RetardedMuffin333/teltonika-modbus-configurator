"""Create TCP Server mappings directly from existing RTU/TCP client requests."""

from __future__ import annotations

from dataclasses import dataclass, field

from .bulk import suggested_register_type
from .models import Project, Request, ServerMapping, permissions_for_function
from .register_allocator import first_free_register_range, register_value_width


_TCP_TYPE_BY_REQUEST_TYPE = {
    "bool": "bool",
    "int8": "int8",
    "uint8": "uint8",
    "int16": "int16",
    "uint16": "uint16",
    "int32": "int32",
    "uint32": "uint32",
    "float32": "float32",
    "ascii": "string",
    "hex": "binary",
    "pdu": "binary",
}


@dataclass(slots=True)
class RequestMappingResult:
    created: list[ServerMapping] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def tcp_mapping_data_type(request: Request) -> str:
    """Return the natural RutOS TCP Server datatype for one client request."""
    register_type = suggested_register_type(request.function)
    if register_type in {"coil", "discrete_input"}:
        return "bool"
    if request.raw_data_type:
        raise ValueError(
            f"{request.name}: raw RutOS datatype {request.raw_data_type!r} cannot be mapped automatically."
        )
    try:
        return _TCP_TYPE_BY_REQUEST_TYPE[request.data_type]
    except KeyError as exc:
        raise ValueError(
            f"{request.name}: request datatype {request.data_type!r} cannot be mapped automatically."
        ) from exc


def _mapping_count(request: Request) -> int:
    return max(1, request.count)


def _unique_mapping_name(project: Project, device_name: str, request_name: str) -> str:
    used = {mapping.name for mapping in project.mappings}
    if request_name not in used:
        return request_name
    base = f"{device_name}_{request_name}"
    if base not in used:
        return base
    ordinal = 2
    while f"{base}_{ordinal}" in used:
        ordinal += 1
    return f"{base}_{ordinal}"


def create_tcp_mappings_from_requests(
    project: Project,
    *,
    device_name: str,
    request_names: list[str],
    start_register: int = 1025,
) -> RequestMappingResult:
    """Create compact collision-free TCP Server mappings for existing requests.

    Each Modbus address space is allocated independently. Existing mappings for
    the same source device/request pair are skipped, making the action safe to
    repeat. 32-bit values reserve two TCP Server addresses per mapped value.
    """
    source = next((d for d in project.devices if d.name == device_name), None)
    if source is None:
        source = next((d for d in project.tcp_clients if d.name == device_name), None)
    if source is None:
        raise ValueError(f"Unknown RTU/TCP client {device_name!r}.")

    request_by_name = {request.name: request for request in source.requests}
    result = RequestMappingResult()

    for request_name in request_names:
        request = request_by_name.get(request_name)
        if request is None:
            result.skipped.append(f"{request_name}: request not found")
            continue
        if any(
            mapping.device == device_name and mapping.request == request_name
            for mapping in project.mappings
        ):
            result.skipped.append(f"{request_name}: TCP Server mapping already exists")
            continue

        try:
            register_type = suggested_register_type(request.function)
            data_type = tcp_mapping_data_type(request)
            count = _mapping_count(request)
            width = count * register_value_width(data_type, register_type)
            register = first_free_register_range(
                project,
                register_type=register_type,
                width=width,
                default=start_register,
            )
            mapping = ServerMapping(
                name=_unique_mapping_name(project, device_name, request_name),
                device=device_name,
                request=request_name,
                register=register,
                register_type=register_type,
                enabled=True,
                permissions=permissions_for_function(request.function),
                data_type=data_type,
                count=count,
            )
        except Exception as exc:
            result.skipped.append(f"{request_name}: {exc}")
            continue

        project.mappings.append(mapping)
        result.created.append(mapping)

    return result
