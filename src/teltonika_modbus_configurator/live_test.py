"""Live Modbus diagnostic helpers for v0.6."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Callable

from .models import Device, Request, TcpClientDevice


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

    @property
    def summary(self) -> str:
        return f"{self.transport.upper()} | {self.device_name} | {self.request.name}"


@dataclass(slots=True)
class LiveTestResult:
    ok: bool
    elapsed_ms: float
    value: str = ""
    raw_response: str = ""
    error: str = ""


def project_test_targets(devices: list[Device], tcp_clients: list[TcpClientDevice]) -> list[LiveTestTarget]:
    targets: list[LiveTestTarget] = []
    for device in devices:
        for request in device.requests:
            targets.append(
                LiveTestTarget(
                    "rtu",
                    device.name,
                    device.slave_id,
                    request,
                    timeout=device.timeout,
                    config_id=device.source_id,
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


def run_timed_test(call: Callable[[], tuple[str, str]]) -> LiveTestResult:
    started = perf_counter()
    try:
        value, raw = call()
        return LiveTestResult(True, (perf_counter() - started) * 1000.0, value=value, raw_response=raw)
    except Exception as exc:
        return LiveTestResult(False, (perf_counter() - started) * 1000.0, error=str(exc))
