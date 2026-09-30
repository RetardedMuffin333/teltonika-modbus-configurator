"""Live validation of proposed import batches before they change a project."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class ImportBatchScanWindow(tk.Toplevel):
    def __init__(self, parent, *, targets, execute):
        super().__init__(parent)
        self.targets = list(targets)
        self.execute = execute
        self.stop_requested = False
        self.title("Scan proposed read batches")
        self.geometry("980x560")
        self.minsize(760, 420)
        self.transient(parent)

        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)
        self.status_var = tk.StringVar(
            value=f"Ready to test {len(self.targets)} proposed physical read batch(es)."
        )
        ttk.Label(outer, textvariable=self.status_var).pack(fill="x", pady=(0, 8))

        frame = ttk.Frame(outer)
        frame.pack(fill="both", expand=True)
        columns = ("request", "fc", "registers", "count", "time", "status")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings")
        for key, title, width in (
            ("request", "Proposed batch", 250), ("fc", "FC", 55),
            ("registers", "Source range", 130), ("count", "Read count", 85),
            ("time", "Time ms", 85), ("status", "Result", 310),
        ):
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, anchor="w")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.tree.tag_configure("ok", foreground="#176b2c")
        self.tree.tag_configure("error", foreground="#a32929")

        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=(8, 0))
        self.scan_button = ttk.Button(actions, text="SCAN BATCHES", command=self.scan)
        self.scan_button.pack(side="left")
        self.stop_button = ttk.Button(actions, text="STOP", command=self.stop, state="disabled")
        self.stop_button.pack(side="left", padx=6)
        ttk.Button(actions, text="Close", command=self.destroy).pack(side="right")
        self.after(80, self.scan)

    def stop(self):
        self.stop_requested = True

    def scan(self):
        self.tree.delete(*self.tree.get_children())
        self.stop_requested = False
        self.scan_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        ok_count = fail_count = 0
        try:
            for index, target in enumerate(self.targets, start=1):
                if self.stop_requested:
                    self.status_var.set(f"Stopped after {index - 1} of {len(self.targets)} batches.")
                    break
                request = target.request
                end = request.register + request.count - 1
                self.status_var.set(f"Scanning {index}/{len(self.targets)}: {request.name}")
                self.update()
                result = self.execute(target)
                if result.ok:
                    ok_count += 1
                    status = "OK"
                    tag = "ok"
                else:
                    fail_count += 1
                    status = result.error or "ERROR"
                    tag = "error"
                self.tree.insert("", "end", values=(
                    request.name, f"FC{int(request.function):02d}",
                    f"{request.register}–{end}", request.count,
                    f"{result.elapsed_ms:.1f}", status,
                ), tags=(tag,))
                self.tree.yview_moveto(1.0)
                self.update()
            else:
                self.status_var.set(
                    f"Scan complete: {ok_count} OK, {fail_count} failed, {len(self.targets)} total. "
                    "Failed batches should be split before import."
                )
        finally:
            self.scan_button.configure(state="normal")
            self.stop_button.configure(state="disabled")
