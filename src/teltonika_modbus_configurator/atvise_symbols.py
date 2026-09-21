"""Export Modbus TCP Server mappings as atvise Connect symbol files.

Known/verified symbol prefixes:

- ``IR``  - integer Input Register
- ``HR``  - integer Holding Register
- ``DI``  - Discrete Input
- ``DA``  - Coil / digital output
- ``IRR`` - FLOAT32 Input Register
- ``HRR`` - FLOAT32 Holding Register
- ``HRD`` - 32-bit Holding Register (signed/unsigned)

Unknown atvise encodings are rejected instead of guessed. FLOAT64 and 32-bit
Input Register symbol encodings remain unverified.
"""

from __future__ import annotations

from .models import Project, ServerMapping


_INTEGER_REGISTER_TYPES = {"int8", "uint8", "int16", "uint16"}


class AtviseSymbolExportError(ValueError):
    """Raised when a project mapping cannot be represented safely in a symbol file."""


def _prefix_for_mapping(mapping: ServerMapping) -> str:
    register_type = mapping.register_type
    data_type = mapping.symbol_data_type or mapping.data_type

    if register_type == "coil":
        return "DA"
    if register_type == "discrete_input":
        return "DI"

    if register_type == "input_register":
        if data_type in _INTEGER_REGISTER_TYPES:
            return "IR"
        if data_type == "float32":
            return "IRR"
        raise AtviseSymbolExportError(
            f"TCP mapping {mapping.name!r} uses input_register/{data_type}; "
            "the atvise Connect symbol prefix for this datatype has not been verified yet."
        )

    if register_type == "holding_register":
        if data_type in _INTEGER_REGISTER_TYPES:
            return "HR"
        if data_type == "float32":
            return "HRR"
        if data_type in {"int32", "uint32"}:
            return "HRD"
        raise AtviseSymbolExportError(
            f"TCP mapping {mapping.name!r} uses holding_register/{data_type}; "
            "the atvise Connect symbol prefix for this datatype has not been verified yet."
        )

    raise AtviseSymbolExportError(
        f"TCP mapping {mapping.name!r} uses unsupported register type {register_type!r}."
    )


def _symbol_line(mapping: ServerMapping) -> str:
    prefix = _prefix_for_mapping(mapping)

    if not mapping.name.strip():
        raise AtviseSymbolExportError("TCP mapping has an empty name.")
    if any(ch in mapping.name for ch in "=\r\n"):
        raise AtviseSymbolExportError(
            f"TCP mapping name {mapping.name!r} contains a character that is unsafe in a symbol file."
        )
    if mapping.register < 0:
        raise AtviseSymbolExportError(
            f"TCP mapping {mapping.name!r} has an invalid register {mapping.register}."
        )

    return f"sym-{mapping.name}={prefix}{mapping.register},"


def _symbol_group(project: Project, device_name: str) -> str:
    source = next(
        (item for item in (*project.devices, *project.tcp_clients) if item.name == device_name),
        None,
    )
    group = ((source.symbol_group if source else None) or device_name).strip()
    if not group:
        raise AtviseSymbolExportError(
            f"TCP mappings for source device {device_name!r} have an empty symbol group."
        )
    if any(ch in group for ch in "[]\r\n"):
        raise AtviseSymbolExportError(
            f"Symbol group {group!r} contains a character that is unsafe in a symbol file."
        )
    return group


def export_atvise_symbols(
    project: Project, *, include_disabled: bool = False, group_by_device: bool = True
) -> str:
    """Return an atvise Connect ``.Symbol`` file for project TCP mappings.

    By default only enabled TCP mappings are exported because disabled mappings
    are not expected to be available through the RutOS Modbus TCP Server.
    """

    mappings = [
        m for m in project.mappings
        if m.export_symbol and (include_disabled or m.enabled)
    ]
    lines = ["[]"]
    if not group_by_device:
        lines.extend(_symbol_line(mapping) for mapping in mappings)
        return "\n".join(lines) + "\n"

    grouped: dict[str, list[ServerMapping]] = {}
    for mapping in mappings:
        grouped.setdefault(mapping.device, []).append(mapping)
    for device_name, device_mappings in grouped.items():
        lines.append(f"[{_symbol_group(project, device_name)}]")
        lines.extend(_symbol_line(mapping) for mapping in device_mappings)
    return "\n".join(lines) + "\n"
