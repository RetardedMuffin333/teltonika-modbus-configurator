"""Device-agnostic configuration models."""

from dataclasses import dataclass, field
from enum import IntEnum


class FunctionCode(IntEnum):
    READ_COILS = 1
    READ_DISCRETE_INPUTS = 2
    READ_HOLDING_REGISTERS = 3
    READ_INPUT_REGISTERS = 4
    WRITE_SINGLE_COIL = 5
    WRITE_SINGLE_HOLDING_REGISTER = 6
    WRITE_MULTIPLE_COILS = 15
    WRITE_MULTIPLE_HOLDING_REGISTERS = 16

    @property
    def is_read(self) -> bool:
        return int(self) in {1, 2, 3, 4}

    @property
    def is_write(self) -> bool:
        return int(self) in {5, 6, 15, 16}


def permissions_for_function(function: FunctionCode) -> str:
    """Return the RutOS Modbus Server access derived from the source request."""
    return "r" if function.is_read else "w"


@dataclass(slots=True)
class SerialConnection:
    name: str
    device: str = "/dev/rs485"
    baudrate: int = 19200
    databits: int = 8
    parity: str = "none"
    stopbits: int = 2
    source_id: str | None = None


@dataclass(slots=True)
class Request:
    name: str
    function: FunctionCode
    register: int
    count: int = 1
    data_type: str = "int16"
    byte_order: str = "high_byte_first"
    enabled: bool = True
    values: str | None = None
    raw_data_type: str | None = None
    source_id: str | None = None

    @property
    def count_or_values(self) -> str:
        if self.function.is_write and self.values is not None:
            return self.values
        return str(self.count)


@dataclass(slots=True)
class Device:
    """Modbus RTU server/slave reached through a local serial connection."""

    name: str
    slave_id: int
    connection: str
    period: int = 10
    timeout: int = 1
    enabled: bool = True
    requests: list[Request] = field(default_factory=list)
    source_id: str | None = None


@dataclass(slots=True)
class TcpClientDevice:
    """Remote Modbus TCP server queried by RutOS Modbus TCP Client.

    RutOS uses ``server_id`` for the Modbus address while the GUI uses the more
    familiar ``unit_id`` label. Both fields are kept synchronized.

    `raw_options` intentionally retains every imported UCI option. v0.3 starts by
    making mixed RTU + TCP live imports lossless; fresh TCP-client generation is
    enabled only after the exact RutOS option names have been verified on hardware.
    """

    name: str
    server_id: int = 1
    host: str = ""
    port: int = 502
    period: int = 60
    timeout: int = 5
    enabled: bool = True
    requests: list[Request] = field(default_factory=list)
    source_id: str | None = None
    raw_options: dict[str, str] = field(default_factory=dict)
    unit_id: int | None = None

    def __setattr__(self, name: str, value) -> None:
        if name == "server_id":
            ivalue = int(value)
            object.__setattr__(self, "server_id", ivalue)
            if hasattr(self, "unit_id"):
                object.__setattr__(self, "unit_id", ivalue)
            return
        if name == "unit_id":
            if value is None:
                current = self.server_id if hasattr(self, "server_id") else 1
                object.__setattr__(self, "unit_id", current)
            else:
                ivalue = int(value)
                object.__setattr__(self, "unit_id", ivalue)
                object.__setattr__(self, "server_id", ivalue)
            return
        object.__setattr__(self, name, value)


@dataclass(slots=True)
class ServerMapping:
    name: str
    device: str
    request: str
    register: int
    register_type: str
    enabled: bool = True
    # Stored for lossless live import/YAML compatibility. The GUI/generator derive
    # the effective value from the source request function (read -> r, write -> w).
    permissions: str = "r"
    data_type: str = "int16"
    count: int = 1
    source_id: str | None = None


@dataclass(slots=True)
class TcpServerSettings:
    port: int = 502
    device_id: int = 101
    enabled: bool = True
    keep_connection: bool = True


@dataclass(slots=True)
class ImportedUciState:
    """Original RutOS packages used as the safe baseline for live round trips."""

    modbus_client: str
    modbus_server: str


@dataclass(slots=True)
class Project:
    connections: list[SerialConnection] = field(default_factory=list)
    devices: list[Device] = field(default_factory=list)
    tcp_clients: list[TcpClientDevice] = field(default_factory=list)
    mappings: list[ServerMapping] = field(default_factory=list)
    tcp_server: TcpServerSettings = field(default_factory=TcpServerSettings)
    source_uci: ImportedUciState | None = None
