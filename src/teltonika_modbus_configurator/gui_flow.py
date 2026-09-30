"""Workflow-oriented desktop layout for the extended configurator."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .gui import ProjectEditor
from .gui_extended import ExtendedProjectEditor


TAB_TITLES = (
    "Serial Connections",
    "RTU Devices",
    "TCP Devices",
    "TCP Server",
    "Server Mappings",
)


class FlowProjectEditor(ExtendedProjectEditor):
    """Extended editor with tabs ordered to match the Modbus data flow."""

    def _build_ui(self):
        style = ttk.Style(self)
        style.configure("ProjectTitle.TLabel", font=("Segoe UI", 11, "bold"))
        style.configure("ProjectSummary.TLabel", foreground="#5c6570")
        style.configure("Treeview", rowheight=24)

        top = ttk.Frame(self, padding=(12, 10))
        top.pack(fill="x")
        project_block = ttk.Frame(top)
        project_block.pack(side="left", fill="x", expand=True)
        self.project_label = ttk.Label(project_block, text="<new>", style="ProjectTitle.TLabel")
        self.project_label.pack(anchor="w")
        self.project_summary = tk.StringVar(value="New empty project")
        ttk.Label(project_block, textvariable=self.project_summary, style="ProjectSummary.TLabel").pack(anchor="w", pady=(2, 0))

        actions = ttk.Frame(top)
        actions.pack(side="right")
        ttk.Button(actions, text="Save Project", command=self.save).pack(side="left", padx=3)
        ttk.Separator(actions, orient="vertical").pack(side="left", fill="y", padx=7)
        ttk.Button(actions, text="Validate", command=self.validate_project).pack(side="left", padx=3)
        ttk.Button(actions, text="Preview UCI", command=self.preview_uci).pack(side="left", padx=3)

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=12, pady=(0, 10))

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
