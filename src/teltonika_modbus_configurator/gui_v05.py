"""v0.5 desktop entry point with profile and atvise Symbol imports."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox

from .carel_import import load_carel_file
from .gui_carel import CarelPreviewWindow
from .gui_symbol import SymbolPreviewWindow
from .gui_usability import UsableCarelProjectEditor
from .symbol_import import load_symbol_file


class V05ProjectEditor(UsableCarelProjectEditor):
    """v0.5 editor retaining v0.4 behavior while extending import workflows."""

    def _build_menu(self):
        super()._build_menu()
        menu = self.nametowidget(self.cget("menu"))
        symbol_menu = tk.Menu(menu, tearoff=False)
        symbol_menu.add_command(label="atvise Connect Symbol file...", command=self.preview_symbol_file)
        menu.add_cascade(label="Symbols", menu=symbol_menu)

    def preview_carel_xls(self):
        """Open any supported Carel tabular export through one normalized loader."""
        filename = filedialog.askopenfilename(
            parent=self,
            title="Open Carel cDesign Modbus export",
            filetypes=[
                ("Carel exports", "*.xls *.xlsx *.csv"),
                ("Excel 97-2003", "*.xls"),
                ("Excel workbook", "*.xlsx"),
                ("CSV", "*.csv"),
                ("All files", "*.*"),
            ],
        )
        if not filename:
            return
        try:
            preview = load_carel_file(filename)
        except Exception as exc:
            messagebox.showerror("Carel import", str(exc), parent=self)
            return
        CarelPreviewWindow(self, preview)

    def preview_symbol_file(self):
        filename = filedialog.askopenfilename(
            parent=self,
            title="Open atvise Connect Symbol file",
            filetypes=[("atvise Symbol files", "*.Symbol *.symbol"), ("All files", "*.*")],
        )
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
