"""v0.8 desktop entry point with guided first-project creation."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from .gui_first_project import FirstProjectWizard
from .gui_v06 import V06ProjectEditor


class V08ProjectEditor(V06ProjectEditor):
    def _build_menu(self):
        super()._build_menu()
        menu = self.nametowidget(self.cget("menu"))
        file_menu_name = menu.entrycget(0, "menu")
        file_menu = menu.nametowidget(file_menu_name)
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
