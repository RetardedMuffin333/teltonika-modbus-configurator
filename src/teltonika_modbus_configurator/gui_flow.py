"""Workflow-oriented desktop layout for the extended configurator."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .gui import ProjectEditor
from .gui_extended import ExtendedProjectEditor


TAB_TITLES = (
    "Modbus Serial Clients",
    "Devices & Requests",
    "Modbus TCP Clients",
    "TCP Server",
    "TCP Server Mappings",
)


class FlowProjectEditor(ExtendedProjectEditor):
    """Extended editor with tabs ordered to match the Modbus data flow."""

    def _build_ui(self):
        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")
        ttk.Label(top, text="Project:").pack(side="left")
        self.project_label = ttk.Label(top, text="<new>")
        self.project_label.pack(side="left", padx=(6, 20))
        ttk.Button(top, text="Validate", command=self.validate_project).pack(side="right", padx=3)
        ttk.Button(top, text="Preview UCI", command=self.preview_uci).pack(side="right", padx=3)
        ttk.Button(top, text="Save", command=self.save).pack(side="right", padx=3)

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # Build in the same order the configuration/data flows through RutOS.
        self._build_connections_tab()
        self.tabs.tab(self.tabs.tabs()[-1], text=TAB_TITLES[0])

        self._build_devices_tab()
        self.tabs.tab(self.tabs.tabs()[-1], text=TAB_TITLES[1])

        self._build_tcp_clients_tab()
        self.tabs.tab(self.tabs.tabs()[-1], text=TAB_TITLES[2])

        # Call the base TCP Server builder directly. ExtendedProjectEditor's
        # override also inserts the TCP Clients tab, which is already built.
        ProjectEditor._build_tcp_server_tab(self)
        self.tabs.tab(self.tabs.tabs()[-1], text=TAB_TITLES[3])

        self._build_mappings_tab()
        self.tabs.tab(self.tabs.tabs()[-1], text=TAB_TITLES[4])

        self.status = tk.StringVar(value="Ready")
        ttk.Label(self, textvariable=self.status, relief="sunken", anchor="w").pack(fill="x", side="bottom")


def main() -> None:
    FlowProjectEditor().mainloop()


if __name__ == "__main__":
    main()
