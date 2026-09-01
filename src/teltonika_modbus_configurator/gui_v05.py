"""v0.5 desktop entry point with profile and atvise Symbol imports."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from .carel_import import load_carel_file
from .gui_carel import CarelPreviewWindow
from .gui_symbol import SymbolPreviewWindow
from .gui_usability import UsableCarelProjectEditor
from .gui_widgets import attach_overlay_scrollbars
from .import_profiles import BUILTIN_IMPORT_PROFILES, CAREL_CDESIGN, get_import_profile
from .symbol_import import load_symbol_file


class ImportProfileDialog(simpledialog.Dialog):
    """Small profile chooser shown before opening a register-table file."""

    def __init__(self, parent):
        self.profile_key: str | None = None
        self.profile_var = tk.StringVar(value=CAREL_CDESIGN.label)
        self._labels = {profile.label: key for key, profile in BUILTIN_IMPORT_PROFILES.items()}
        super().__init__(parent, "Register table import")

    def body(self, master):
        ttk.Label(master, text="Import profile:").grid(row=0, column=0, padx=8, pady=8, sticky="w")
        combo = ttk.Combobox(master, textvariable=self.profile_var, values=list(self._labels), state="readonly", width=30)
        combo.grid(row=0, column=1, padx=8, pady=8, sticky="ew")
        ttk.Label(master, text="Carel cDesign uses the hardware-tested Index +1 default. Generic Modbus tables keep addresses unchanged.", wraplength=430, justify="left").grid(row=1, column=0, columnspan=2, padx=8, pady=(0, 8), sticky="w")
        master.columnconfigure(1, weight=1)
        return combo

    def apply(self):
        self.profile_key = self._labels[self.profile_var.get()]


class V05ProjectEditor(UsableCarelProjectEditor):
    """v0.5 editor retaining v0.4 behavior while extending import workflows."""

    @staticmethod
    def _delete_menu_label(menu: tk.Menu, label: str) -> None:
        end = menu.index("end")
        if end is None:
            return
        for index in range(end + 1):
            try:
                if menu.entrycget(index, "label") == label:
                    menu.delete(index)
                    return
            except tk.TclError:
                continue

    def _build_menu(self):
        super()._build_menu()
        menu = self.nametowidget(self.cget("menu"))
        self._delete_menu_label(menu, "Carel")
        import_menu = tk.Menu(menu, tearoff=False)
        import_menu.add_command(label="Register table (XLS/XLSX/CSV)...", command=self.preview_register_table)
        import_menu.add_command(label="atvise Connect Symbol file...", command=self.preview_symbol_file)
        menu.add_cascade(label="Import", menu=import_menu)

    def _build_connections_tab(self):
        super()._build_connections_tab()
        attach_overlay_scrollbars(self.connections_tree)

    def _build_devices_tab(self):
        super()._build_devices_tab()
        attach_overlay_scrollbars(self.devices_tree)
        attach_overlay_scrollbars(self.requests_tree)

    def _build_tcp_clients_tab(self):
        super()._build_tcp_clients_tab()
        attach_overlay_scrollbars(self.tcp_clients_tree)
        attach_overlay_scrollbars(self.tcp_client_requests_tree)

    def _build_mappings_tab(self):
        super()._build_mappings_tab()
        attach_overlay_scrollbars(self.mappings_tree)

    def preview_carel_xls(self):
        self.preview_register_table()

    def preview_register_table(self):
        chooser = ImportProfileDialog(self)
        if not chooser.profile_key:
            return
        profile = get_import_profile(chooser.profile_key)
        filename = filedialog.askopenfilename(parent=self, title=f"Open {profile.label} Modbus export", filetypes=[("Register tables", "*.xls *.xlsx *.csv"), ("Excel 97-2003", "*.xls"), ("Excel workbook", "*.xlsx"), ("CSV", "*.csv"), ("All files", "*.*")])
        if not filename:
            return
        try:
            preview = load_carel_file(filename, profile=profile)
        except Exception as exc:
            messagebox.showerror("Register table import", str(exc), parent=self)
            return
        if not preview.rows:
            messagebox.showerror("Register table import", f"No register rows were detected with the {profile.label} profile.", parent=self)
            return
        window = CarelPreviewWindow(self, preview)
        window.title(f"Register table import - {profile.label}")
        window.add_one_var.set(profile.default_add_one_to_index)
        self._generalize_register_preview_labels(window)

    @staticmethod
    def _generalize_register_preview_labels(window) -> None:
        stack = list(window.winfo_children())
        while stack:
            widget = stack.pop()
            stack.extend(widget.winfo_children())
            try:
                text = widget.cget("text")
            except tk.TclError:
                continue
            if text == "Carel Index + 1 for RutOS request address":
                widget.configure(text="Add +1 to source register for RutOS request address")

    def preview_symbol_file(self):
        filename = filedialog.askopenfilename(parent=self, title="Open atvise Connect Symbol file", filetypes=[("atvise Symbol files", "*.Symbol *.symbol"), ("All files", "*.*")])
        if not filename:
            return
        try:
            preview = load_symbol_file(filename)
        except Exception as exc:
            messagebox.showerror("Symbol import", str(exc), parent=self)
            return
        if not preview.rows:
            messagebox.showerror("Symbol import", "No atvise symbols were detected in this file.", parent=self)
            return
        SymbolPreviewWindow(self, preview)


def main() -> None:
    V05ProjectEditor().mainloop()


if __name__ == "__main__":
    main()
