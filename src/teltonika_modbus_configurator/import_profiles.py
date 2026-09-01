"""Reusable register-table import profiles.

Profiles describe how a vendor export names its important columns and how source
variable names should be normalized. File-format loading stays separate from
vendor semantics so the same profile can be used with XLS, XLSX, or CSV input.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


NameSanitizer = Callable[[str], str]


def identity_name(value: str) -> str:
    return value.strip()


def carel_name(value: str) -> str:
    """Normalize cDesign structure/array syntax for RutOS/SCADA names."""
    name = value.strip().replace(".", "_")
    return name.replace("[", "").replace("]", "")


@dataclass(frozen=True, slots=True)
class ImportProfile:
    key: str
    label: str
    name_aliases: tuple[str, ...]
    register_aliases: tuple[str, ...]
    modbus_type_aliases: tuple[str, ...]
    size_aliases: tuple[str, ...]
    data_type_aliases: tuple[str, ...]
    access_aliases: tuple[str, ...]
    sanitize_name: NameSanitizer = identity_name
    default_add_one_to_index: bool = False


CAREL_CDESIGN = ImportProfile(
    key="carel_cdesign",
    label="Carel cDesign",
    name_aliases=("variable name", "variable acronym", "name", "variable", "symbol", "tag", "parameter"),
    register_aliases=("index", "register", "address", "addr", "modbus address"),
    modbus_type_aliases=("types", "modbus type", "register type", "area"),
    size_aliases=("size", "length", "count"),
    data_type_aliases=("datatype", "data type", "type", "format"),
    access_aliases=("direction", "access", "read/write", "r/w", "permission", "mode"),
    sanitize_name=carel_name,
    # Hardware-tested cDesign project used zero-based exported indices.
    default_add_one_to_index=True,
)


GENERIC_MODBUS_TABLE = ImportProfile(
    key="generic_modbus_table",
    label="Generic Modbus table",
    name_aliases=("name", "tag", "symbol", "node", "point", "variable", "description"),
    register_aliases=("register", "address", "addr", "offset", "index", "modbus address"),
    modbus_type_aliases=("area", "register type", "modbus type", "memory", "table"),
    size_aliases=("size", "length", "count", "register count", "words"),
    data_type_aliases=("data type", "datatype", "format", "encoding", "type"),
    access_aliases=("access", "direction", "rights", "permission", "read/write", "r/w"),
    sanitize_name=identity_name,
    default_add_one_to_index=False,
)


BUILTIN_IMPORT_PROFILES: dict[str, ImportProfile] = {
    CAREL_CDESIGN.key: CAREL_CDESIGN,
    GENERIC_MODBUS_TABLE.key: GENERIC_MODBUS_TABLE,
}


def get_import_profile(key: str) -> ImportProfile:
    try:
        return BUILTIN_IMPORT_PROFILES[key]
    except KeyError as exc:
        raise ValueError(f"Unknown import profile: {key}") from exc
