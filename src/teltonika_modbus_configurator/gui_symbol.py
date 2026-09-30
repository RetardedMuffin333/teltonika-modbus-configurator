"""GUI preview/import workflow for atvise Connect .Symbol files."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from .gui_import_scan import ImportBatchScanWindow
from .live_test import target_for_request
from .read_batching import batch_read_items
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

        ttk.Label(options, text="Existing names:").grid(row=1, column=0, padx=6, pady=(0, 6), sticky="w")
        self.conflict_var = tk.StringVar(value="Skip existing")
        ttk.Combobox(
            options,
            textvariable=self.conflict_var,
            values=("Skip existing", "Replace matching on selected device"),
            state="readonly",
            width=36,
        ).grid(row=1, column=1, columnspan=3, padx=6, pady=(0, 6), sticky="w")

        ttk.Label(
            options,
            text="Symbol addresses are treated as physical device registers. Connection IP/slave/serial settings come from the selected existing device.",
        ).grid(row=2, column=0, columnspan=7, padx=6, pady=(0, 6), sticky="w")

        self.write_companions_var = tk.BooleanVar(value=False)
        self.write_only_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            options,
            text="Write requests only (do not create reads or read mappings)",
            variable=self.write_only_var,
        ).grid(row=3, column=0, columnspan=7, padx=6, pady=(0, 6), sticky="w")
        ttk.Checkbutton(
            options,
            text="Create SCADA write companions for selected DA/HR/HRR/HRD symbols",
            variable=self.write_companions_var,
        ).grid(row=4, column=0, columnspan=7, padx=6, pady=(0, 6), sticky="w")

        self.batch_writes_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            options,
            text="Batch write requests (FC15/FC16; test on target hardware first)",
            variable=self.batch_writes_var,
        ).grid(row=5, column=0, columnspan=7, padx=6, pady=(0, 6), sticky="w")

        self.read_mode_var = tk.StringVar(value="batched")
        ttk.Label(options, text="Read import mode:").grid(row=6, column=0, padx=6, pady=(0, 6), sticky="w")
        ttk.Radiobutton(
            options,
            text="Batched (recommended; FC03/FC04 up to 100 registers, FC01/FC02 up to 1000 bits)",
            variable=self.read_mode_var,
            value="batched",
        ).grid(row=6, column=1, columnspan=4, padx=6, pady=(0, 6), sticky="w")
        ttk.Radiobutton(
            options,
            text="Register by register",
            variable=self.read_mode_var,
            value="individual",
        ).grid(row=6, column=5, columnspan=2, padx=6, pady=(0, 6), sticky="w")

        filters = ttk.Frame(self)
        filters.pack(fill="x", padx=10, pady=(0, 6))
        ttk.Label(filters, text="Symbol type:").pack(side="left")
        self.type_var = tk.StringVar(value="All")
        types = ["All"] + sorted({row.symbol_type for row in preview.rows})
        ttk.Combobox(filters, textvariable=self.type_var, values=types, state="readonly", width=12).pack(side="left", padx=5)
        ttk.Button(filters, text="Apply filter", command=self.refresh).pack(side="left", padx=4)
        ttk.Button(filters, text="Select all visible", command=lambda: self.tree.selection_set(self.tree.get_children())).pack(side="left", padx=4)
        ttk.Button(filters, text="Clear selection", command=lambda: self.tree.selection_remove(self.tree.selection())).pack(side="left", padx=4)

        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        self.tree = ttk.Treeview(
            tree_frame,
            columns=("name", "type", "source", "fc", "dtype", "server", "status"),
            show="headings", selectmode="extended",
        )
        for key, title, width in (
            ("name", "Node name", 390), ("type", "Symbol", 65), ("source", "Source addr", 85),
            ("fc", "FC", 45), ("dtype", "Data type", 90), ("server", "TCP Server", 125), ("status", "Status", 270),
        ):
            self.tree.heading(key, text=title); self.tree.column(key, width=width, anchor="w")

        yscroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        xscroll = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        self.tree.bind("<MouseWheel>", self._on_mousewheel)
        self.tree.bind("<Shift-MouseWheel>", self._on_shift_mousewheel)

        footer = ttk.Frame(self); footer.pack(fill="x", padx=10, pady=(0, 10))
        self.info_var = tk.StringVar(value="Preview only. Build a plan before importing.")
        ttk.Label(footer, textvariable=self.info_var).pack(side="left")
        ttk.Button(footer, text="Close", command=self.destroy).pack(side="right")
        self.import_button = ttk.Button(footer, text="Import selected ready rows", command=self.apply_plan, state="disabled")
        self.import_button.pack(side="right", padx=8)
        self.scan_button = ttk.Button(footer, text="Scan proposed batches", command=self.scan_batches, state="disabled")
        self.scan_button.pack(side="right")
        self.refresh()

    def _on_mousewheel(self, event):
        self.tree.yview_scroll(int(-event.delta / 120), "units")
        return "break"

    def _on_shift_mousewheel(self, event):
        self.tree.xview_scroll(int(-event.delta / 120), "units")
        return "break"

    def _visible(self, row):
        return self.type_var.get() == "All" or row.symbol_type == self.type_var.get()

    def refresh(self):
        y_position = self.tree.yview()[0] if self.tree.get_children() else 0.0
        for iid in self.tree.get_children(): self.tree.delete(iid)
        self.plan_by_iid = {}
        if not self.plan:
            for row in self.preview.rows:
                if self._visible(row):
                    self.tree.insert("", "end", values=(row.name, row.symbol_type, row.register, "", "", "", "Parsed"))
            self.tree.yview_moveto(y_position)
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
        self.tree.yview_moveto(y_position)
        self.info_var.set(f"Visible plan: {ready} ready, {skipped} skipped. Select the rows you want to import.")
        self.import_button.configure(state="normal" if ready else "disabled")
        self.scan_button.configure(state="normal" if ready else "disabled")

    def build_plan(self):
        if not self.device_var.get():
            messagebox.showerror("Symbol import", "Create or select an RTU/TCP target device first.", parent=self); return
        try:
            offset = int(self.offset_var.get())
            start = int(self.start_var.get())
            self.plan = build_symbol_import_plan(
                self.parent.project, self.preview.rows, device_name=self.device_var.get(),
                source_address_offset=offset, mapping_start=start,
                conflict_policy="replace" if self.conflict_var.get().startswith("Replace") else "skip",
                write_only=self.write_only_var.get(),
            )
        except Exception as exc:
            messagebox.showerror("Symbol import", str(exc), parent=self); return
        self.refresh()

    def scan_batches(self):
        if self.read_mode_var.get() != "batched" or self.write_only_var.get():
            messagebox.showinfo(
                "Batch scan", "Select Batched read import mode; write-only imports have no read batches to scan.",
                parent=self,
            )
            return
        selected = [self.plan_by_iid[iid] for iid in self.tree.selection() if iid in self.plan_by_iid]
        indexes = selected or list(self.plan_by_iid.values())
        items = [
            self.plan[index] for index in indexes
            if self.plan[index].request is not None and self.plan[index].mapping is not None
        ]
        if not items:
            messagebox.showinfo("Batch scan", "Build a plan containing ready read rows first.", parent=self)
            return
        device_name = self.device_var.get()
        device = next(
            source for source in (*self.parent.project.devices, *self.parent.project.tcp_clients)
            if source.name == device_name
        )
        requests, _mappings, _items = batch_read_items(device.requests, items)
        execute = self.parent.prompt_live_test_executor()
        if execute is None:
            return
        targets = [
            target_for_request(
                self.parent.project.devices, self.parent.project.tcp_clients,
                self.parent.project.connections, device_name=device_name, request=request,
            )
            for request in requests
        ]
        ImportBatchScanWindow(self, targets=targets, execute=execute)

    def apply_plan(self):
        selected = [self.plan_by_iid[iid] for iid in self.tree.selection() if iid in self.plan_by_iid]
        items = [self.plan[i] for i in selected if self.plan[i].request is not None and self.plan[i].mapping is not None]
        if not items:
            messagebox.showinfo("Symbol import", "Select at least one ready row.", parent=self); return
        batch_reads = self.read_mode_var.get() == "batched"
        write_only = self.write_only_var.get()
        create_writes = self.write_companions_var.get() or write_only
        mode = "bounded batch requests" if batch_reads else "one request per symbol"
        writeable = sum(
            item.mapping is not None and item.mapping.register_type in {"coil", "holding_register"}
            for item in items
        )
        write_note = ""
        if create_writes:
            write_note = f"\nCreate {writeable} independent SCADA write companion(s) for writable symbols."
        if write_only:
            write_note = f"\nCreate {writeable} write request(s) only; no read requests will be added."
        if create_writes and self.batch_writes_var.get():
            write_note += "\nGroup writes into FC15/FC16 blocks."
        if not messagebox.askyesno(
            "Symbol import",
            f"Import {len(items)} selected symbols into {self.device_var.get()} using {mode}?\n\n"
            f"{write_note}\n"
            "This changes only the project; it does not deploy to RutOS.",
            parent=self,
        ):
            return
        try:
            before_writes = sum(request.function.is_write for source in (*self.parent.project.devices, *self.parent.project.tcp_clients) for request in source.requests)
            count = apply_symbol_import_plan(
                self.parent.project, items, device_name=self.device_var.get(), mapping_start=int(self.start_var.get()),
                batch_reads=batch_reads,
                create_write_companions=create_writes,
                write_only=write_only,
                batch_writes=create_writes and self.batch_writes_var.get(),
            )
            after_writes = sum(request.function.is_write for source in (*self.parent.project.devices, *self.parent.project.tcp_clients) for request in source.requests)
        except Exception as exc:
            messagebox.showerror("Symbol import", str(exc), parent=self); return
        self.parent.mark_dirty()
        self.parent.refresh_all()
        messagebox.showinfo(
            "Symbol import",
            f"Imported {count} symbols.\nCreated {after_writes - before_writes} write companions.",
            parent=self,
        )
        self.destroy()
