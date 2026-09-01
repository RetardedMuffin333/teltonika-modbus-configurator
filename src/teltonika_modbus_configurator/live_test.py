"""Live Modbus diagnostic helpers for v0.6."""

from __future__ import annotations

from dataclasses import dataclass, replace
from time import perf_counter
from typing import Callable

from .models import Device, FunctionCode, Request, SerialConnection, TcpClientDevice


READ_FUNCTIONS = {1, 2, 3, 4}


@dataclass(slots=True)
class LiveTestTarget:
    transport: str
    device_name: str
    device_id: int
    request: Request
    host: str | None = None
    port: int | None = None
    timeout: float | None = None
    config_id: int | str | None = None
    serial_type: str | None = None
    baudrate: int | None = None
    databits: int | None = None
    parity: str | None = None
    stopbits: int | None = None
    flowcontrol: str | None = None

    @property
    def summary(self) -> str:
        return f"{self.transport.upper()} | {self.device_name} | {self.request.name}"

    @property
    def device_summary(self) -> str:
        return f"{self.transport.upper()} | {self.device_name}"


@dataclass(slots=True)
class LiveTestResult:
    ok: bool
    elapsed_ms: float
    value: str = ""
    raw_response: str = ""
    error: str = ""


def project_test_targets(
    devices: list[Device],
    tcp_clients: list[TcpClientDevice],
    connections: list[SerialConnection] | None = None,
) -> list[LiveTestTarget]:
    targets: list[LiveTestTarget] = []
    connection_by_name = {connection.name: connection for connection in (connections or [])}
    for device in devices:
        connection = connection_by_name.get(device.connection)
        for request in device.requests:
            targets.append(
                LiveTestTarget(
                    "rtu",
                    device.name,
                    device.slave_id,
                    request,
                    timeout=device.timeout,
                    config_id=device.source_id,
                    serial_type=connection.device if connection else "/dev/rs485",
                    baudrate=connection.baudrate if connection else None,
                    databits=connection.databits if connection else None,
                    parity=connection.parity if connection else None,
                    stopbits=connection.stopbits if connection else None,
                    flowcontrol="none",
                )
            )
    for device in tcp_clients:
        for request in device.requests:
            targets.append(
                LiveTestTarget(
                    "tcp", device.name, device.server_id, request,
                    device.host, device.port, device.timeout, device.source_id,
                )
            )
    return targets


def device_templates(targets: list[LiveTestTarget]) -> list[LiveTestTarget]:
    """Return one transport template per configured Modbus device."""
    templates: list[LiveTestTarget] = []
    seen: set[tuple[str, str]] = set()
    for target in targets:
        key = (target.transport, target.device_name)
        if key in seen:
            continue
        seen.add(key)
        templates.append(target)
    return templates


def read_targets_for_device(targets: list[LiveTestTarget], template: LiveTestTarget) -> list[LiveTestTarget]:
    """Return enabled FC01-FC04 requests belonging to one selected device."""
    return [
        target
        for target in targets
        if target.transport == template.transport
        and target.device_name == template.device_name
        and target.request.enabled
        and int(target.request.function) in READ_FUNCTIONS
    ]


def make_adhoc_target(
    template: LiveTestTarget,
    *,
    function: int,
    register: int,
    count: int,
    data_type: str,
    byte_order: str,
) -> LiveTestTarget:
    """Build a temporary read target while inheriting the real device transport."""
    if function not in READ_FUNCTIONS:
        raise ValueError("Ad-hoc live testing currently supports FC01-FC04 reads only")
    if register < 0:
        raise ValueError("Register must be 0 or greater")
    if count < 1:
        raise ValueError("Count must be at least 1")
    if function in {1, 2}:
        data_type = "bool"
        byte_order = "none"
    request = Request(
        name="Ad-hoc",
        function=FunctionCode(function),
        register=register,
        count=count,
        data_type=data_type,
        byte_order=byte_order,
        enabled=True,
    )
    return replace(template, request=request)


def run_timed_test(call: Callable[[], tuple[str, str]]) -> LiveTestResult:
    started = perf_counter()
    try:
        value, raw = call()
        return LiveTestResult(True, (perf_counter() - started) * 1000.0, value=value, raw_response=raw)
    except Exception as exc:
        return LiveTestResult(False, (perf_counter() - started) * 1000.0, error=str(exc))
