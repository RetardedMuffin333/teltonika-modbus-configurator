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


@dataclass(slots=True)
class SerialConnection:
    name: str
    device: str = "/dev/rs485"
    baudrate: int = 19200
    databits: int = 8
    parity: str = "none"
    stopbits: int = 2


@dataclass(slots=True)
class Request:
    name: str
    function: FunctionCode
    register: int
    count: int = 1
    data_type: str = "int16"
    byte_order: str = "high_byte_first"
    enabled: bool = True
    # For FC05/06/15/16 RutOS reuses reg_count as the value/value list.
    # Keeping it separate from count avoids confusing a write value with a read length.
    values: str | None = None

    @property
    def count_or_values(self) -> str:
        if self.function.is_write and self.values is not None:
            return self.values
        return str(self.count)


@dataclass(slots=True)
class Device:
    name: str
    slave_id: int
    connection: str
    period: int = 10
    timeout: int = 1
    enabled: bool = True
    requests: list[Request] = field(default_factory=list)


@dataclass(slots=True)
class ServerMapping:
    name: str
    device: str
    request: str
    register: int
    register_type: str
    enabled: bool = True
    permissions: str = "r"  # r, w, rw
    data_type: str = "int16"
    count: int = 1


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
    mappings: list[ServerMapping] = field(default_factory=list)
    tcp_server: TcpServerSettings = field(default_factory=TcpServerSettings)
    source_uci: ImportedUciState | None = None
