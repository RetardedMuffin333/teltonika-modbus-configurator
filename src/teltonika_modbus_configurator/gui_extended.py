"""Extended desktop entry point with bulk generation tools."""

from __future__ import annotations

import tkinter as tk

from .gui import ProjectEditor
from .gui_bulk import BulkGeneratorWindow


class ExtendedProjectEditor(ProjectEditor):
    def _build_menu(self):
        super()._build_menu()
        menu = self.nametowidget(self.cget("menu"))
        bulk_menu = tk.Menu(menu, tearoff=False)
        bulk_menu.add_command(label="Bulk Device Generator...", command=self.open_bulk_generator)
        menu.add_cascade(label="Bulk", menu=bulk_menu)

    def open_bulk_generator(self):
        if not self.project.connections:
            from tkinter import messagebox

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


def main():
    app = ExtendedProjectEditor()
    app.mainloop()


if __name__ == "__main__":
    main()
