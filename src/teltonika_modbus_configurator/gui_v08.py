"""v0.8 desktop entry point with guided first-project creation."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from .gui import enabled_mark
from .gui_first_project import FirstProjectWizard
from .gui_validation import ValidationResultsWindow
from .gui_v06 import V06ProjectEditor
from .validator import validate_project


class V08ProjectEditor(V06ProjectEditor):
    def _build_devices_tab(self):
        super()._build_devices_tab()
        self._configure_grouped_request_tree(self.requests_tree)

    def _build_tcp_clients_tab(self):
        super()._build_tcp_clients_tab()
        self._configure_grouped_request_tree(self.tcp_client_requests_tree)

    @staticmethod
    def _configure_grouped_request_tree(tree):
        tree.configure(show="tree headings")
        tree.heading("#0", text="")
        tree.column("#0", width=28, minwidth=28, stretch=False)
        tree.tag_configure("symbol_alias", foreground="#245b8a")

    def _refresh_grouped_requests(self, tree, *, device_name, requests):
        opened = {iid for iid in tree.get_children("") if tree.item(iid, "open")}
        tree.delete(*tree.get_children())
        groups = {
            "requests::read": ("Read requests", []),
            "requests::write": ("Write requests", []),
        }
        for index, request in enumerate(requests):
            groups["requests::read" if request.function.is_read else "requests::write"][1].append((index, request))

        for group_iid, (label, group_requests) in groups.items():
            if not group_requests:
                continue
            tree.insert(
                "", "end", iid=group_iid, open=(group_iid in opened or not opened),
                values=(label, "", "", "", "", "", ""),
            )
            for index, request in group_requests:
                count_or_values = request.values if request.function.is_write else request.count
                dtype = request.raw_data_type or request.data_type
                tree.insert(
                    group_iid, "end", iid=str(index),
                    values=(request.name, int(request.function), request.register, count_or_values,
                            dtype, request.byte_order, enabled_mark(request.enabled)),
                )
                aliases = [
                    mapping for mapping in self.project.mappings
                    if not mapping.deploy and mapping.device == device_name and mapping.request == request.name
                ]
                for alias_index, alias in enumerate(aliases):
                    tree.insert(
                        str(index), "end", iid=f"request-alias::{device_name}::{index}::{alias_index}",
                        values=(f"↳ {alias.name}", alias.permissions,
                                f"TCP {alias.register}", "symbol", alias.symbol_data_type or alias.data_type,
                                "", enabled_mark(alias.enabled)), tags=("symbol_alias",),
                    )

    def refresh_requests(self):
        if not hasattr(self, "requests_tree"):
            return
        index = self.selected_device_index()
        if index is None or index >= len(self.project.devices):
            self.requests_tree.delete(*self.requests_tree.get_children())
            return
        device = self.project.devices[index]
        self._refresh_grouped_requests(self.requests_tree, device_name=device.name, requests=device.requests)

    def refresh_tcp_client_requests(self):
        if not hasattr(self, "tcp_client_requests_tree"):
            return
        index = self.selected_tcp_client_index()
        if index is None or index >= len(self.project.tcp_clients):
            self.tcp_client_requests_tree.delete(*self.tcp_client_requests_tree.get_children())
            return
        device = self.project.tcp_clients[index]
        self._refresh_grouped_requests(
            self.tcp_client_requests_tree, device_name=device.name, requests=device.requests,
        )

    def validate_project(self):
        messages = validate_project(self.project)
        if not messages:
            messagebox.showinfo("Validation", "Validation PASS - no errors found.", parent=self)
            self.status.set("Validation PASS")
            return True
        ValidationResultsWindow(self, messages)
        self.status.set(f"Validation returned {len(messages)} message(s)")
        return not any(message.level == "error" for message in messages)

    def _build_menu(self):
        super()._build_menu()
        menu = self.nametowidget(self.cget("menu"))
        file_menu = self._find_submenu(menu, "File")
        if file_menu is None:
            raise RuntimeError("The File menu could not be found.")
        file_menu.insert_command(1, label="First Project Wizard...", command=self.open_first_project_wizard)
        file_menu.insert_separator(2)

    def open_first_project_wizard(self):
        has_content = bool(
            self.project.connections or self.project.devices or self.project.tcp_clients
            or self.project.mappings or self.path is not None or self.dirty
        )
        if has_content and not messagebox.askyesno(
            "Replace current project",
            "The wizard creates a new project and replaces the project currently open in the editor.\n\nContinue?",
            parent=self,
        ):
            return
        wizard = FirstProjectWizard(self)
        if wizard.result is None:
            return
        options, project = wizard.result
        self.project = project
        self.path = None
        self.dirty = True
        self.refresh_all()
        self.status.set("First project created; add/import requests, validate, and save")
        if options.next_action == "register_table":
            self.after(100, self.preview_register_table)
        elif options.next_action == "symbol_file":
            self.after(100, self.preview_symbol_file)


def main() -> None:
    V08ProjectEditor().mainloop()


if __name__ == "__main__":
    main()
