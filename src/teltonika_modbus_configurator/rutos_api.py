"""Small RutOS Web API client used by the v0.6 live Modbus tester."""

from __future__ import annotations

import json
from typing import Any

import requests
import urllib3

from .live_test import LiveTestTarget, run_timed_test
from .uci_generator import _request_data_type


class RutOSApiClient:
    def __init__(self, host: str, username: str, password: str, *, https: bool = False, verify_tls: bool = False, timeout: float = 10.0):
        scheme = "https" if https else "http"
        self.base_url = f"{scheme}://{host.rstrip('/')}/api"
        self.username = username
        self.password = password
        self.verify_tls = verify_tls
        self.timeout = timeout
        self.token: str | None = None
        if https and not verify_tls:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def login(self) -> None:
        response = requests.post(
            f"{self.base_url}/login",
            json={"username": self.username, "password": self.password},
            timeout=self.timeout,
            verify=self.verify_tls,
        )
        response.raise_for_status()
        payload = response.json()
        token = payload.get("data", {}).get("token")
        if not payload.get("success") or not token:
            raise RuntimeError(_api_error(payload, "RutOS API login failed"))
        self.token = token

    def _headers(self) -> dict[str, str]:
        if not self.token:
            self.login()
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    def post(self, endpoint: str, data: dict[str, Any]) -> dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/{endpoint.lstrip('/')}",
            headers=self._headers(),
            json={"data": data},
            timeout=self.timeout,
            verify=self.verify_tls,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("success") is False:
            raise RuntimeError(_api_error(payload, "RutOS API request failed"))
        return payload

    def test_tcp(self, target: LiveTestTarget):
        if target.transport != "tcp":
            raise ValueError("TCP live transport can only test TCP targets")
        request = target.request
        data = {
            "server_id": str(target.device_id),
            "timeout": str(target.timeout or 5),
            "function": str(int(request.function)),
            "first_reg": str(request.register),
            "reg_count": str(request.count),
            "data_type": _request_data_type(request),
            "no_brackets": "0",
            "dev_ipaddr": str(target.host),
            "port": str(target.port or 502),
            "delay": "0",
        }
        endpoint_id = str(target.config_id or 1)
        return self.post(f"modbus/client/tcp/{endpoint_id}/requests/actions/test_request", data)


def execute_tcp_test(client: RutOSApiClient, target: LiveTestTarget):
    def call():
        payload = client.test_tcp(target)
        raw = json.dumps(payload, indent=2, ensure_ascii=False)
        return _extract_value(payload), raw

    return run_timed_test(call)


def _extract_value(payload: Any) -> str:
    data = payload.get("data") if isinstance(payload, dict) else payload
    if isinstance(data, dict):
        for key in ("value", "result", "response", "data"):
            if key in data:
                value = data[key]
                return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    if data is None:
        return ""
    return data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)


def _api_error(payload: dict[str, Any], fallback: str) -> str:
    errors = payload.get("errors") or payload.get("error")
    if errors:
        return f"{fallback}: {errors}"
    return fallback
