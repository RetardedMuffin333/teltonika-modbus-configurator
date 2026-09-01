"""v0.5 desktop entry point with multi-format Carel import."""

from __future__ import annotations

from tkinter import filedialog, messagebox

from .carel_import import load_carel_file
from .gui_carel import CarelPreviewWindow
from .gui_usability import UsableCarelProjectEditor


class V05ProjectEditor(UsableCarelProjectEditor):
    """v0.5 editor retaining v0.4 behavior while extending import formats."""

    def _build_menu(self):
        # Reuse the existing menu but redirect the Carel command through this
        # class by overriding preview_carel_xls below.
        super()._build_menu()

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


def main() -> None:
    V05ProjectEditor().mainloop()


if __name__ == "__main__":
    main()
