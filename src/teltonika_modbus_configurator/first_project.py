"""Testable project construction for the First Project Wizard."""

from __future__ import annotations

from dataclasses import dataclass

from .models import Device, Project, SerialConnection, TcpClientDevice, TcpServerSettings


PROJECT_TYPES = {"rtu", "tcp", "mixed"}
NEXT_ACTIONS = {"none", "register_table", "symbol_file"}


@dataclass(slots=True)
class FirstProjectOptions:
    project_type: str = "tcp"
    tcp_server_port: int = 502
    tcp_server_device_id: int = 101
    keep_connection: bool = True
    serial_name: str = "RS485"
    serial_device: str = "/dev/rs485"
    baudrate: int = 19200
    databits: int = 8
    parity: str = "none"
    stopbits: int = 2
    rtu_device_name: str = "RTU_Device_1"
    rtu_slave_id: int = 1
    rtu_period: int = 10
    rtu_timeout: int = 1
    tcp_device_name: str = "TCP_Device_1"
    tcp_host: str = "192.168.2.20"
    tcp_port: int = 502
    tcp_unit_id: int = 1
    tcp_period: int = 10
    tcp_timeout: int = 1
    next_action: str = "none"


def validate_first_project_options(options: FirstProjectOptions) -> list[str]:
    errors: list[str] = []
    if options.project_type not in PROJECT_TYPES:
        errors.append("Select RTU, TCP, or Mixed project type.")
    if options.next_action not in NEXT_ACTIONS:
        errors.append("Unknown next step.")
    if not 1 <= options.tcp_server_port <= 65535:
        errors.append("TCP Server port must be 1..65535.")
    if not 1 <= options.tcp_server_device_id <= 247:
        errors.append("TCP Server Device ID must be 1..247.")

    if options.project_type in {"rtu", "mixed"}:
        if not options.serial_name.strip():
            errors.append("Serial connection name is required.")
        if not options.serial_device.strip():
            errors.append("Serial device path is required.")
        if options.baudrate <= 0:
            errors.append("Baudrate must be positive.")
        if options.serial_device not in {"/dev/rs232", "/dev/rs485"}:
            errors.append("Serial device must be /dev/rs232 or /dev/rs485.")
        if options.databits not in {5, 6, 7, 8}:
            errors.append("Data bits must be 5, 6, 7, or 8.")
        if options.parity not in {"none", "even", "odd", "mark", "space"}:
            errors.append("Parity must be none, even, odd, mark, or space.")
        if options.stopbits not in {1, 2}:
            errors.append("Stop bits must be 1 or 2.")
        if not options.rtu_device_name.strip():
            errors.append("RTU device name is required.")
        if not 1 <= options.rtu_slave_id <= 247:
            errors.append("RTU Slave ID must be 1..247.")
        if options.rtu_period < 1 or options.rtu_timeout < 1:
            errors.append("RTU period and timeout must be positive.")

    if options.project_type in {"tcp", "mixed"}:
        if not options.tcp_device_name.strip():
            errors.append("TCP device name is required.")
        if not options.tcp_host.strip():
            errors.append("TCP device host/IP is required.")
        if not 1 <= options.tcp_port <= 65535:
            errors.append("TCP device port must be 1..65535.")
        if not 0 <= options.tcp_unit_id <= 247:
            errors.append("TCP Unit ID must be 0..247.")
        if options.tcp_period < 1 or options.tcp_timeout < 1:
            errors.append("TCP period and timeout must be positive.")

    names = []
    if options.project_type in {"rtu", "mixed"}:
        names.append(options.rtu_device_name.strip())
    if options.project_type in {"tcp", "mixed"}:
        names.append(options.tcp_device_name.strip())
    if len(names) != len(set(names)):
        errors.append("RTU and TCP device names must be different.")
    return errors


def build_first_project(options: FirstProjectOptions) -> Project:
    errors = validate_first_project_options(options)
    if errors:
        raise ValueError("Invalid First Project options:\n- " + "\n- ".join(errors))

    project = Project(tcp_server=TcpServerSettings(
        port=options.tcp_server_port,
        device_id=options.tcp_server_device_id,
        enabled=True,
        keep_connection=options.keep_connection,
    ))
    if options.project_type in {"rtu", "mixed"}:
        connection_name = options.serial_name.strip()
        project.connections.append(SerialConnection(
            name=connection_name,
            device=options.serial_device.strip(),
            baudrate=options.baudrate,
            databits=options.databits,
            parity=options.parity,
            stopbits=options.stopbits,
        ))
        project.devices.append(Device(
            name=options.rtu_device_name.strip(),
            slave_id=options.rtu_slave_id,
            connection=connection_name,
            period=options.rtu_period,
            timeout=options.rtu_timeout,
            enabled=True,
        ))
    if options.project_type in {"tcp", "mixed"}:
        project.tcp_clients.append(TcpClientDevice(
            name=options.tcp_device_name.strip(),
            host=options.tcp_host.strip(),
            port=options.tcp_port,
            server_id=options.tcp_unit_id,
            period=options.tcp_period,
            timeout=options.tcp_timeout,
            enabled=True,
        ))
    return project
