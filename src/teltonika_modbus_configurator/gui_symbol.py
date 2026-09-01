"""GUI preview/import workflow for atvise Connect .Symbol files."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from .symbol_import import apply_symbol_import_plan, build_symbol_import_plan


class SymbolPreviewWindow(tk.Toplevel):
    def __init__(self, parent, preview):
        super().__init__(parent)
        self.parent = parent
        self.preview = preview
        self.plan = []
        self.plan_by_iid = {}
        self.title("atvise Connect Symbol import")
        self.geometry("1320x800")
        self.transient(parent)

        ttk.Label(
            self,
            text=f"File: {preview.path}\nSymbols: {len(preview.rows)}   Unrecognized lines: {preview.ignored_lines}",
            justify="left",
        ).pack(fill="x", padx=10, pady=(10, 5))

        options = ttk.LabelFrame(self, text="Import options")
        options.pack(fill="x", padx=10, pady=(0, 7))
        ttk.Label(options, text="Target device:").grid(row=0, column=0, padx=6, pady=6, sticky="w")
        targets = [d.name for d in parent.project.devices] + [d.name for d in parent.project.tcp_clients]
        self.device_var = tk.StringVar(value=targets[0] if targets else "")
        ttk.Combobox(options, textvariable=self.device_var, values=targets, state="readonly", width=28).grid(row=0, column=1, padx=6, pady=6)

        ttk.Label(options, text="Source address offset:").grid(row=0, column=2, padx=(16, 4), pady=6)
        self.offset_var = tk.StringVar(value="0")
        ttk.Entry(options, textvariable=self.offset_var, width=7).grid(row=0, column=3, padx=4, pady=6)
        ttk.Label(options, text="TCP Server mapping start:").grid(row=0, column=4, padx=(16, 4), pady=6)
        self.start_var = tk.StringVar(value="1025")
        ttk.Entry(options, textvariable=self.start_var, width=8).grid(row=0, column=5, padx=4, pady=6)
        ttk.Button(options, text="Build import plan", command=self.build_plan).grid(row=0, column=6, padx=10, pady=6)

        ttk.Label(
            options,
            text="Symbol addresses are treated as physical device registers. Connection IP/slave/serial settings come from the selected existing device.",
        ).grid(row=1, column=0, columnspan=7, padx=6, pady=(0, 6), sticky="w")

        filters = ttk.Frame(self)
        filters.pack(fill="x", padx=10, pady=(0, 6))
        ttk.Label(filters, text="Symbol type:").pack(side="left")
        self.type_var = tk.StringVar(value="All")
        types = ["All"] + sorted({row.symbol_type for row in preview.rows})
        ttk.Combobox(filters, textvariable=self.type_var, values=types, state="readonly", width=12).pack(side="left", padx=5)
        ttk.Button(filters, text="Apply filter", command=self.refresh).pack(side="left", padx=4)
        ttk.Button(filters, text="Select all visible", command=lambda: self.tree.selection_set(self.tree.get_children())).pack(side="left", padx=4)
        ttk.Button(filters, text="Clear selection", command=lambda: self.tree.selection_remove(self.tree.selection())).pack(side="left", padx=4)

        self.tree = ttk.Treeview(
            self,
            columns=("name", "type", "source", "fc", "dtype", "server", "status"),
            show="headings", selectmode="extended",
        )
        for key, title, width in (
            ("name", "Node name", 390), ("type", "Symbol", 65), ("source", "Source addr", 85),
            ("fc", "FC", 45), ("dtype", "Data type", 90), ("server", "TCP Server", 125), ("status", "Status", 270),
        ):
            self.tree.heading(key, text=title); self.tree.column(key, width=width, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        footer = ttk.Frame(self); footer.pack(fill="x", padx=10, pady=(0, 10))
        self.info_var = tk.StringVar(value="Preview only. Build a plan before importing.")
        ttk.Label(footer, textvariable=self.info_var).pack(side="left")
        ttk.Button(footer, text="Close", command=self.destroy).pack(side="right")
        self.import_button = ttk.Button(footer, text="Import selected ready rows", command=self.apply_plan, state="disabled")
        self.import_button.pack(side="right", padx=8)
        self.refresh()

    def _visible(self, row):
        return self.type_var.get() == "All" or row.symbol_type == self.type_var.get()

    def refresh(self):
        for iid in self.tree.get_children(): self.tree.delete(iid)
        self.plan_by_iid = {}
        if not self.plan:
            for row in self.preview.rows:
                if self._visible(row):
                    self.tree.insert("", "end", values=(row.name, row.symbol_type, row.register, "", "", "", "Parsed"))
            return
        ready = skipped = 0
        for index, item in enumerate(self.plan):
            row = item.source
            if not self._visible(row): continue
            if item.request and item.mapping:
                ready += 1
                server = f"{item.mapping.register_type}:{item.mapping.register}"
                values = (row.name, row.symbol_type, item.request.register, int(item.request.function), item.request.data_type, server, item.status)
            else:
                skipped += 1
                values = (row.name, row.symbol_type, row.register, "", "", "", item.status)
            iid = self.tree.insert("", "end", values=values)
            self.plan_by_iid[iid] = index
        self.info_var.set(f"Visible plan: {ready} ready, {skipped} skipped. Select the rows you want to import.")
        self.import_button.configure(state="normal" if ready else "disabled")

    def build_plan(self):
        if not self.device_var.get():
            messagebox.showerror("Symbol import", "Create or select an RTU/TCP target device first.", parent=self); return
        try:
            offset = int(self.offset_var.get())
            start = int(self.start_var.get())
            self.plan = build_symbol_import_plan(
                self.parent.project, self.preview.rows, device_name=self.device_var.get(),
                source_address_offset=offset, mapping_start=start,
            )
        except Exception as exc:
            messagebox.showerror("Symbol import", str(exc), parent=self); return
        self.refresh()

    def apply_plan(self):
        selected = [self.plan_by_iid[iid] for iid in self.tree.selection() if iid in self.plan_by_iid]
        items = [self.plan[i] for i in selected if self.plan[i].request is not None and self.plan[i].mapping is not None]
        if not items:
            messagebox.showinfo("Symbol import", "Select at least one ready row.", parent=self); return
        try:
            count = apply_symbol_import_plan(
                self.parent.project, items, device_name=self.device_var.get(), mapping_start=int(self.start_var.get())
            )
        except Exception as exc:
            messagebox.showerror("Symbol import", str(exc), parent=self); return
        self.parent.mark_dirty()
        self.parent.refresh_all()
        messagebox.showinfo("Symbol import", f"Imported {count} symbols.", parent=self)
        self.destroy()
