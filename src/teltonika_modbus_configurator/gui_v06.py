"""v0.6 desktop entry point with live Modbus diagnostics."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog

from .gui_live_test import LiveModbusTesterWindow
from .gui_v05 import V05ProjectEditor
from .live_test import run_timed_test
from .rutos_api import RutOSApiClient, execute_tcp_test


class V06ProjectEditor(V05ProjectEditor):
    """v0.6 editor adding read-only live Modbus diagnostics."""

    def _build_menu(self):
        super()._build_menu()
        menu = self.nametowidget(self.cget("menu"))
        tools = tk.Menu(menu, tearoff=False)
        tools.add_command(label="Live Modbus Tester...", command=self.open_live_modbus_tester)
        menu.add_cascade(label="Tools", menu=tools)

    def open_live_modbus_tester(self):
        host = simpledialog.askstring("RutOS API", "Gateway IP / hostname:", initialvalue="192.168.2.1", parent=self)
        if not host:
            return
        username = simpledialog.askstring("RutOS API", "WebUI/API username:", initialvalue="admin", parent=self) or "admin"
        password = simpledialog.askstring("RutOS API", "WebUI/API password:", show="*", parent=self)
        if password is None:
            return
        https = messagebox.askyesno(
            "RutOS API protocol",
            "Use HTTPS?\n\nChoose No for HTTP (typical on older RUT956 firmware).",
            parent=self,
        )
        client = RutOSApiClient(host, username, password, https=https, verify_tls=False)

        def execute(target):
            if target.transport == "tcp":
                return execute_tcp_test(client, target)
            return run_timed_test(lambda: (_ for _ in ()).throw(RuntimeError(
                "Serial/RTU API execution is the next transport slice; TCP live testing is enabled now."
            )))

        LiveModbusTesterWindow(self, self.project, execute=execute)


def main() -> None:
    V06ProjectEditor().mainloop()


if __name__ == "__main__":
    main()
