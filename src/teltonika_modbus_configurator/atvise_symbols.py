"""Export Modbus TCP Server mappings as atvise Connect symbol files.

Known/verified symbol prefixes:

- ``IR``  - integer Input Register
- ``HR``  - integer Holding Register
- ``DI``  - Discrete Input
- ``DA``  - Coil / digital output
- ``IRR`` - FLOAT32 Input Register
- ``HRR`` - FLOAT32 Holding Register
- ``HRD`` - FLOAT64 Holding Register

Unknown atvise encodings are rejected instead of guessed. This is important for
32/64-bit integer values and FLOAT64 Input Registers, whose Connect prefixes have
not yet been verified against a known-good symbol file.
"""

from __future__ import annotations

from .models import Project, ServerMapping


_INTEGER_REGISTER_TYPES = {"int8", "uint8", "int16", "uint16"}


class AtviseSymbolExportError(ValueError):
    """Raised when a project mapping cannot be represented safely in a symbol file."""


def _prefix_for_mapping(mapping: ServerMapping) -> str:
    register_type = mapping.register_type
    data_type = mapping.data_type

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
        if data_type == "float64":
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


def export_atvise_symbols(project: Project, *, include_disabled: bool = False) -> str:
    """Return an atvise Connect ``.Symbol`` file for project TCP mappings.

    By default only enabled TCP mappings are exported because disabled mappings
    are not expected to be available through the RutOS Modbus TCP Server.
    """

    mappings = [m for m in project.mappings if include_disabled or m.enabled]
    lines = ["[]"]
    lines.extend(_symbol_line(mapping) for mapping in mappings)
    return "\n".join(lines) + "\n"
