"""v0.6 desktop entry point with live Modbus diagnostics."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog

from .gui_live_test import LiveModbusTesterWindow
from .gui_v05 import V05ProjectEditor
from .rutos_api import RutOSApiClient, execute_live_test


class V06ProjectEditor(V05ProjectEditor):
    """v0.6 editor adding read-only live Modbus diagnostics."""

    @staticmethod
    def _find_submenu(menu: tk.Menu, label: str) -> tk.Menu | None:
        end = menu.index("end")
        if end is None:
            return None
        for index in range(end + 1):
            try:
                if menu.entrycget(index, "label") != label:
                    continue
                submenu_name = menu.entrycget(index, "menu")
                return menu.nametowidget(submenu_name) if submenu_name else None
            except tk.TclError:
                continue
        return None

    def _build_menu(self):
        super()._build_menu()
        menu = self.nametowidget(self.cget("menu"))
        tools = self._find_submenu(menu, "Tools")
        if tools is None:
            tools = tk.Menu(menu, tearoff=False)
            menu.add_cascade(label="Tools", menu=tools)
        else:
            tools.add_separator()
        tools.add_command(label="Live Modbus Tester...", command=self.open_live_modbus_tester)

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
        LiveModbusTesterWindow(
            self,
            self.project,
            execute=lambda target: execute_live_test(client, target),
        )


def main() -> None:
    V06ProjectEditor().mainloop()


if __name__ == "__main__":
    main()
