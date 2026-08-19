"""Serialize a Project into an explicit, canonical YAML representation."""

from __future__ import annotations

import yaml

from .models import Project


def project_to_dict(project: Project) -> dict:
    data = {
        "connections": [
            {
                "name": c.name,
                "type": "serial",
                "device": c.device,
                "baudrate": c.baudrate,
                "databits": c.databits,
                "parity": c.parity,
                "stopbits": c.stopbits,
            }
            for c in project.connections
        ],
        "tcp_server": {
            "port": project.tcp_server.port,
            "device_id": project.tcp_server.device_id,
            "enabled": project.tcp_server.enabled,
            "keep_connection": project.tcp_server.keep_connection,
        },
        "devices": [
            {
                "name": d.name,
                "connection": d.connection,
                "slave_id": d.slave_id,
                "period": d.period,
                "timeout": d.timeout,
                "enabled": d.enabled,
                "requests": [
                    {
                        "name": r.name,
                        "function": int(r.function),
                        "register": r.register,
                        "count": r.count,
                        "data_type": r.data_type,
                        "byte_order": r.byte_order,
                        "enabled": r.enabled,
                        **({"values": r.values} if r.values is not None else {}),
                    }
                    for r in d.requests
                ],
            }
            for d in project.devices
        ],
        "mappings": [
            {
                "name": m.name,
                "device": m.device,
                "request": m.request,
                "register_type": m.register_type,
                "register": m.register,
                "enabled": m.enabled,
                "permissions": m.permissions,
                "data_type": m.data_type,
                "count": m.count,
            }
            for m in project.mappings
        ],
    }
    if project.source_uci is not None:
        data["source_uci"] = {
            "modbus_client": project.source_uci.modbus_client,
            "modbus_server": project.source_uci.modbus_server,
        }
    return data


def dump_project(project: Project) -> str:
    return yaml.safe_dump(data=project_to_dict(project), sort_keys=False, allow_unicode=True, default_flow_style=False)
