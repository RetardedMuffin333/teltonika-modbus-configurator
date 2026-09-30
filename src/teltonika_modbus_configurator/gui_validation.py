"""Structured project-validation result window."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .gui_widgets import tree_with_scrollbars


class ValidationResultsWindow(tk.Toplevel):
    def __init__(self, parent, messages):
        super().__init__(parent)
        self.title("Validation results")
        self.geometry("980x520")
        self.minsize(720, 360)
        self.transient(parent)

        counts = {
            level: sum(message.level == level for message in messages)
            for level in ("error", "warning", "info")
        }
        ttk.Label(
            self,
            text=(f"Errors: {counts['error']}    Warnings: {counts['warning']}    "
                  f"Information: {counts['info']}"),
        ).pack(fill="x", padx=10, pady=(10, 6))

        frame, tree = tree_with_scrollbars(
            self, columns=("severity", "object", "problem"), show="headings", selectmode="browse",
        )
        for key, title, width in (
            ("severity", "Severity", 90), ("object", "Object", 260), ("problem", "Problem", 580),
        ):
            tree.heading(key, text=title)
            tree.column(key, width=width, anchor="w")
        frame.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        for message in messages:
            object_name, separator, problem = message.message.partition(": ")
            if not separator:
                object_name, problem = "Project", message.message
            tree.insert(
                "", "end", values=(message.level.upper(), object_name, problem),
                tags=(message.level,),
            )
        tree.tag_configure("error", foreground="#a32929")
        tree.tag_configure("warning", foreground="#9a6500")
        tree.tag_configure("info", foreground="#245b8a")

        footer = ttk.Frame(self)
        footer.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(footer, text="Close", command=self.destroy).pack(side="right")
