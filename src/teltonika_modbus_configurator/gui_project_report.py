"""Project report viewer and text export."""

from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


class ProjectReportWindow(tk.Toplevel):
    def __init__(self, parent, *, title: str, report: str, suggested_name: str):
        super().__init__(parent)
        self.title(title)
        self.geometry("980x760")
        self.report = report
        self.suggested_name = suggested_name

        frame = ttk.Frame(self, padding=10)
        frame.pack(fill="both", expand=True)
        area = tk.Text(frame, wrap="none", font=("Consolas", 10))
        y = ttk.Scrollbar(frame, orient="vertical", command=area.yview)
        x = ttk.Scrollbar(frame, orient="horizontal", command=area.xview)
        area.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        area.grid(row=0, column=0, sticky="nsew")
        y.grid(row=0, column=1, sticky="ns")
        x.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        area.insert("1.0", report)
        area.configure(state="disabled")

        buttons = ttk.Frame(self, padding=(10, 0, 10, 10))
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Save as TXT...", command=self._save).pack(side="left")
        ttk.Button(buttons, text="Copy to clipboard", command=self._copy).pack(side="left", padx=6)
        ttk.Button(buttons, text="Close", command=self.destroy).pack(side="right")

    def _save(self):
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Save project report",
            initialfile=self.suggested_name,
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            Path(path).write_text(self.report, encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("Save failed", str(exc), parent=self)
            return
        messagebox.showinfo("Project report", f"Report saved to:\n{path}", parent=self)

    def _copy(self):
        self.clipboard_clear()
        self.clipboard_append(self.report)
        self.update_idletasks()
        messagebox.showinfo("Project report", "Report copied to the clipboard.", parent=self)
