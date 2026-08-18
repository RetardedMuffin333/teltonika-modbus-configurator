"""Export Modbus TCP Server mappings as atvise Connect symbol files.

The format implemented here is based on a known-good atvise Connect symbol file:

[]
sym-Status_Temp=IR1025,
sym-Cmd_Setpoint=HR1080,

For v1 we intentionally support only Input Registers and Holding Registers,
which are the register types verified against the user's Connect setup.
"""

from __future__ import annotations

from .models import Project, ServerMapping


ATVISE_PREFIXES = {
    "input_register": "IR",
    "holding_register": "HR",
}


class AtviseSymbolExportError(ValueError):
    """Raised when a project cannot be represented safely in a v1 symbol file."""


def _symbol_line(mapping: ServerMapping) -> str:
    try:
        prefix = ATVISE_PREFIXES[mapping.register_type]
    except KeyError as exc:
        raise AtviseSymbolExportError(
            f"TCP mapping {mapping.name!r} uses {mapping.register_type!r}; "
            "v1 atvise symbol export currently supports only input_register and holding_register."
        ) from exc

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
    """Return an atvise Connect `.Symbol` file for project TCP mappings.

    By default only enabled TCP mappings are exported because disabled mappings
    are not expected to be readable from the RutOS Modbus TCP Server.
    """

    mappings = [m for m in project.mappings if include_disabled or m.enabled]
    lines = ["[]"]
    lines.extend(_symbol_line(mapping) for mapping in mappings)
    return "\n".join(lines) + "\n"
