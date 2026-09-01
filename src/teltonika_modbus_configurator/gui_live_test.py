"""Read-only live Modbus diagnostic window for v0.6."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from .live_test import LiveTestTarget, project_test_targets


READ_FUNCTIONS = {1, 2, 3, 4}


class LiveModbusTesterWindow(tk.Toplevel):
    def __init__(self, parent, project, execute=None):
        super().__init__(parent)
        self.project = project
        self.execute = execute
        self.targets = project_test_targets(project.devices, project.tcp_clients, project.connections)
        self.target_by_label = {target.summary: target for target in self.targets}

        self.title("Live Modbus Tester")
        self.geometry("720x520")
        self.transient(parent)

        self.target_var = tk.StringVar()
        self.protocol_var = tk.StringVar(value="-")
        self.device_id_var = tk.StringVar(value="-")
        self.endpoint_var = tk.StringVar(value="-")
        self.function_var = tk.StringVar(value="-")
        self.register_var = tk.StringVar(value="-")
        self.count_var = tk.StringVar(value="-")
        self.dtype_var = tk.StringVar(value="-")
        self.order_var = tk.StringVar(value="-")
        self.status_var = tk.StringVar(value="Select a read request to test.")
        self.elapsed_var = tk.StringVar(value="-")
        self.value_var = tk.StringVar(value="-")

        self._build_ui()
        if self.targets:
            first = next((t for t in self.targets if int(t.request.function) in READ_FUNCTIONS), self.targets[0])
            self.target_var.set(first.summary)
            self._target_changed()
        else:
            self.test_button.configure(state="disabled")
            self.status_var.set("This project has no RTU or TCP client requests.")

    def _build_ui(self):
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Existing project request:").grid(row=0, column=0, sticky="w")
        self.target_combo = ttk.Combobox(outer, textvariable=self.target_var, values=[target.summary for target in self.targets], state="readonly", width=65)
        self.target_combo.grid(row=0, column=1, columnspan=3, sticky="ew", padx=(8, 0))
        self.target_combo.bind("<<ComboboxSelected>>", lambda _event: self._target_changed())
        fields = (("Protocol", self.protocol_var), ("Device / Server ID", self.device_id_var), ("Endpoint", self.endpoint_var), ("Function", self.function_var), ("Register", self.register_var), ("Count", self.count_var), ("Data type", self.dtype_var), ("Byte order", self.order_var))
        for index, (label, variable) in enumerate(fields, start=1):
            column = 0 if index <= 4 else 2
            row = index if index <= 4 else index - 4
            ttk.Label(outer, text=f"{label}:").grid(row=row, column=column, sticky="w", pady=5)
            ttk.Label(outer, textvariable=variable).grid(row=row, column=column + 1, sticky="w", padx=(8, 20), pady=5)
        ttk.Separator(outer).grid(row=5, column=0, columnspan=4, sticky="ew", pady=10)
        self.test_button = ttk.Button(outer, text="TEST REQUEST", command=self._test)
        self.test_button.grid(row=6, column=0, columnspan=4, pady=(0, 12))
        ttk.Label(outer, text="Status:").grid(row=7, column=0, sticky="nw")
        ttk.Label(outer, textvariable=self.status_var, wraplength=520, justify="left").grid(row=7, column=1, columnspan=3, sticky="w", padx=(8, 0))
        ttk.Label(outer, text="Response time:").grid(row=8, column=0, sticky="w", pady=5)
        ttk.Label(outer, textvariable=self.elapsed_var).grid(row=8, column=1, sticky="w", padx=(8, 0))
        ttk.Label(outer, text="Decoded value:").grid(row=9, column=0, sticky="w", pady=5)
        ttk.Label(outer, textvariable=self.value_var).grid(row=9, column=1, columnspan=3, sticky="w", padx=(8, 0))
        ttk.Label(outer, text="Raw response:").grid(row=10, column=0, sticky="nw", pady=(5, 0))
        self.raw = tk.Text(outer, height=8, wrap="word", font=("Consolas", 9))
        self.raw.grid(row=10, column=1, columnspan=3, sticky="nsew", padx=(8, 0), pady=(5, 0))
        self.raw.configure(state="disabled")
        outer.columnconfigure(1, weight=1)
        outer.columnconfigure(3, weight=1)
        outer.rowconfigure(10, weight=1)

    def _selected_target(self) -> LiveTestTarget | None:
        return self.target_by_label.get(self.target_var.get())

    def _target_changed(self):
        target = self._selected_target()
        if target is None:
            return
        request = target.request
        self.protocol_var.set(target.transport.upper())
        self.device_id_var.set(str(target.device_id))
        if target.transport == "tcp":
            self.endpoint_var.set(f"{target.host}:{target.port}")
        else:
            serial = f"{target.baudrate or '?'} {target.databits or '?'}{(target.parity or '?')[0].upper()}{target.stopbits or '?'}"
            self.endpoint_var.set(f"RS485 via RutOS ({serial})")
        self.function_var.set(f"FC{int(request.function):02d}")
        self.register_var.set(str(request.register))
        self.count_var.set(str(request.count))
        self.dtype_var.set(request.data_type)
        self.order_var.set(request.byte_order)
        if int(request.function) in READ_FUNCTIONS:
            self.test_button.configure(state="normal" if self.execute else "disabled")
            self.status_var.set("Ready for read-only test." if self.execute else "Transport not connected yet; request preview is ready.")
        else:
            self.test_button.configure(state="disabled")
            self.status_var.set("Write requests are intentionally disabled in the first v0.6 tester.")

    def _set_raw(self, text: str):
        self.raw.configure(state="normal")
        self.raw.delete("1.0", "end")
        self.raw.insert("1.0", text)
        self.raw.configure(state="disabled")

    def _test(self):
        target = self._selected_target()
        if target is None or self.execute is None:
            return
        if int(target.request.function) not in READ_FUNCTIONS:
            messagebox.showwarning("Live Modbus Tester", "Only FC01-FC04 reads are enabled in this version.", parent=self)
            return
        self.status_var.set("Testing...")
        self.elapsed_var.set("-")
        self.value_var.set("-")
        self._set_raw("")
        self.update_idletasks()
        result = self.execute(target)
        self.elapsed_var.set(f"{result.elapsed_ms:.1f} ms")
        if result.ok:
            self.status_var.set("OK")
            self.value_var.set(result.value or "-")
            self._set_raw(result.raw_response)
        else:
            self.status_var.set(f"ERROR: {result.error}")
            self.value_var.set("-")
            self._set_raw(result.raw_response)
