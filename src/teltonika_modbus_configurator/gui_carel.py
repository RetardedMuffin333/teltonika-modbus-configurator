"""v0.4 GUI entry point with Carel cDesign import preview."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .carel_import import load_carel_xls
from .gui_scada import ScadaProjectEditor


class CarelProjectEditor(ScadaProjectEditor):
    def _build_menu(self):
        super()._build_menu()
        menu = self.nametowidget(self.cget("menu"))
        import_menu = tk.Menu(menu, tearoff=False)
        import_menu.add_command(label="Carel cDesign XLS preview...", command=self.preview_carel_xls)
        menu.add_cascade(label="Carel", menu=import_menu)

    def preview_carel_xls(self):
        filename = filedialog.askopenfilename(
            parent=self,
            title="Open Carel cDesign Modbus export",
            filetypes=[("Carel / Excel 97-2003", "*.xls"), ("All files", "*.*")],
        )
        if not filename:
            return
        try:
            preview = load_carel_xls(filename)
        except Exception as exc:
            messagebox.showerror("Carel import preview", str(exc), parent=self)
            return
        CarelPreviewWindow(self, preview)


class CarelPreviewWindow(tk.Toplevel):
    def __init__(self, parent, preview):
        super().__init__(parent)
        self.title("Carel cDesign XLS import preview")
        self.geometry("1050x620")
        self.transient(parent)

        summary = (
            f"File: {preview.path}\n"
            f"Sheets: {', '.join(preview.sheets) or '<none>'}\n"
            f"Detected header row: {preview.header_row or '<not detected>'}   "
            f"Candidate rows: {len(preview.rows)}"
        )
        ttk.Label(self, text=summary, justify="left").pack(fill="x", padx=10, pady=(10, 6))

        if preview.headers:
            ttk.Label(self, text="Detected columns: " + " | ".join(preview.headers), wraplength=1000).pack(
                fill="x", padx=10, pady=(0, 8)
            )

        tree = ttk.Treeview(
            self,
            columns=("sheet", "row", "name", "register", "dtype", "access"),
            show="headings",
        )
        for key, title, width in (
            ("sheet", "Sheet", 100), ("row", "Row", 55), ("name", "Name", 330),
            ("register", "Register", 110), ("dtype", "Data type", 150), ("access", "Access", 120),
        ):
            tree.heading(key, text=title)
            tree.column(key, width=width, anchor="w")
        tree.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        for item in preview.rows:
            tree.insert("", "end", values=(item.sheet, item.row_number, item.name, item.register, item.data_type, item.access))

        footer = ttk.Frame(self)
        footer.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Label(
            footer,
            text="Preview only — v0.4 does not create project requests from this file yet.",
        ).pack(side="left")
        ttk.Button(footer, text="Close", command=self.destroy).pack(side="right")


def main() -> None:
    CarelProjectEditor().mainloop()


if __name__ == "__main__":
    main()
