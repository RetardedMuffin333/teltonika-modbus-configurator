"""Extended desktop entry point with deployment, bulk, and export tools."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox

from .atvise_symbols import export_atvise_symbols
from .gui_bulk import BulkGeneratorWindow
from .gui_deploy import DeploymentEditor


class ExtendedProjectEditor(DeploymentEditor):
    def _build_menu(self):
        super()._build_menu()
        menu = self.nametowidget(self.cget("menu"))

        bulk_menu = tk.Menu(menu, tearoff=False)
        bulk_menu.add_command(label="Bulk Device Generator...", command=self.open_bulk_generator)
        menu.add_cascade(label="Bulk", menu=bulk_menu)

        export_menu = tk.Menu(menu, tearoff=False)
        export_menu.add_command(
            label="atvise Connect Symbol file...",
            command=self.export_atvise_symbol_file,
        )
        menu.add_cascade(label="Export", menu=export_menu)

    def open_bulk_generator(self):
        if not self.project.connections:
            messagebox.showerror(
                "Bulk generator",
                "Create or import at least one serial connection first.",
                parent=self,
            )
            return
        BulkGeneratorWindow(self, self.project, self._bulk_applied)

    def _bulk_applied(self):
        self.mark_dirty()
        self.refresh_all()
        self.status.set("Bulk batch added to project; validate and save before deployment")

    def export_atvise_symbol_file(self):
        try:
            text = export_atvise_symbols(self.project)
        except Exception as exc:
            messagebox.showerror("atvise symbol export", str(exc), parent=self)
            return

        if text.strip() == "[]":
            messagebox.showerror(
                "atvise symbol export",
                "There are no enabled TCP mappings to export.",
                parent=self,
            )
            return

        default_name = self.path.stem if self.path else "Teltonika_Modbus"
        filename = filedialog.asksaveasfilename(
            parent=self,
            title="Export atvise Connect Symbol file",
            defaultextension=".Symbol",
            initialfile=f"{default_name}.Symbol",
            filetypes=[("atvise Connect Symbol", "*.Symbol"), ("All files", "*.*")],
        )
        if not filename:
            return

        try:
            with open(filename, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
            count = sum(1 for m in self.project.mappings if m.enabled)
            self.status.set(f"Exported {count} atvise symbol(s) to {filename}")
            messagebox.showinfo(
                "atvise symbol export",
                f"Exported {count} symbol(s).\n\n{filename}",
                parent=self,
            )
        except Exception as exc:
            messagebox.showerror("atvise symbol export", str(exc), parent=self)


def main():
    app = ExtendedProjectEditor()
    app.mainloop()


if __name__ == "__main__":
    main()
