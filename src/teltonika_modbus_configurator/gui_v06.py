"""v0.6 desktop entry point with live Modbus diagnostics."""

from __future__ import annotations

import tkinter as tk

from .gui_live_test import LiveModbusTesterWindow
from .gui_v05 import V05ProjectEditor


class V06ProjectEditor(V05ProjectEditor):
    """v0.6 editor adding read-only live Modbus diagnostics."""

    def _build_menu(self):
        super()._build_menu()
        menu = self.nametowidget(self.cget("menu"))
        tools = tk.Menu(menu, tearoff=False)
        tools.add_command(label="Live Modbus Tester...", command=self.open_live_modbus_tester)
        menu.add_cascade(label="Tools", menu=tools)

    def open_live_modbus_tester(self):
        LiveModbusTesterWindow(self, self.project)


def main() -> None:
    V06ProjectEditor().mainloop()


if __name__ == "__main__":
    main()
