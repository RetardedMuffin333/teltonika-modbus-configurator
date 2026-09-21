"""Read-only live Modbus diagnostic window for v0.6."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from .live_test import (
    READ_FUNCTIONS,
    LiveTestTarget,
    device_templates,
    make_adhoc_target,
    make_adhoc_write_target,
    project_test_targets,
    read_targets_for_device,
    write_targets,
)


FUNCTION_CHOICES = {
    "FC01 Read Coils": 1,
    "FC02 Read Discrete Inputs": 2,
    "FC03 Read Holding Registers": 3,
    "FC04 Read Input Registers": 4,
}
DATA_TYPES = ("int16", "uint16", "int32", "uint32", "float32")
BYTE_ORDERS = ("high_byte_first", "low_byte_first", "1234", "2143", "3412", "4321")
WRITE_FUNCTION_CHOICES = {
    "FC05 Write Single Coil": 5,
    "FC06 Write Single Register": 6,
    "FC15 Write Multiple Coils": 15,
    "FC16 Write Multiple Registers": 16,
}


class LiveModbusTesterWindow(tk.Toplevel):
    def __init__(self, parent, project, execute=None):
        super().__init__(parent)
        self.project = project
        self.execute = execute
        self.targets = project_test_targets(project.devices, project.tcp_clients, project.connections)
        self.target_by_label = {target.summary: target for target in self.targets}
        self.write_target_list = write_targets(self.targets)
        self.write_target_by_label = {target.summary: target for target in self.write_target_list}
        self.templates = device_templates(self.targets)
        self.template_by_label = {target.device_summary: target for target in self.templates}
        self.scan_stop_requested = False

        self.title("Live Modbus Tester")
        self.geometry("940x700")
        self.minsize(820, 600)
        self.transient(parent)

        self.status_var = tk.StringVar(value="Ready.")
        self.elapsed_var = tk.StringVar(value="-")
        self.value_var = tk.StringVar(value="-")

        self._build_ui()

    def _build_ui(self):
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)
        notebook = ttk.Notebook(outer)
        notebook.pack(fill="both", expand=True)
        self._build_existing_tab(notebook)
        self._build_adhoc_tab(notebook)
        self._build_write_tab(notebook)
        self._build_scan_tab(notebook)

    def _build_existing_tab(self, notebook):
        tab = ttk.Frame(notebook, padding=12)
        notebook.add(tab, text="Existing Request")
        self.target_var = tk.StringVar()
        self.protocol_var = tk.StringVar(value="-")
        self.device_id_var = tk.StringVar(value="-")
        self.endpoint_var = tk.StringVar(value="-")
        self.function_var = tk.StringVar(value="-")
        self.register_var = tk.StringVar(value="-")
        self.count_var = tk.StringVar(value="-")
        self.dtype_var = tk.StringVar(value="-")
        self.order_var = tk.StringVar(value="-")

        ttk.Label(tab, text="Existing project request:").grid(row=0, column=0, sticky="w")
        self.target_combo = ttk.Combobox(tab, textvariable=self.target_var, values=[t.summary for t in self.targets], state="readonly", width=70)
        self.target_combo.grid(row=0, column=1, columnspan=3, sticky="ew", padx=(8, 0))
        self.target_combo.bind("<<ComboboxSelected>>", lambda _event: self._target_changed())

        fields = (("Protocol", self.protocol_var), ("Device / Server ID", self.device_id_var), ("Endpoint", self.endpoint_var), ("Function", self.function_var), ("Register", self.register_var), ("Count", self.count_var), ("Data type", self.dtype_var), ("Byte order", self.order_var))
        for index, (label, variable) in enumerate(fields, start=1):
            column = 0 if index <= 4 else 2
            row = index if index <= 4 else index - 4
            ttk.Label(tab, text=f"{label}:").grid(row=row, column=column, sticky="w", pady=5)
            ttk.Label(tab, textvariable=variable).grid(row=row, column=column + 1, sticky="w", padx=(8, 20), pady=5)

        ttk.Separator(tab).grid(row=5, column=0, columnspan=4, sticky="ew", pady=10)
        self.test_button = ttk.Button(tab, text="TEST REQUEST", command=self._test_existing)
        self.test_button.grid(row=6, column=0, columnspan=4, pady=(0, 10))
        self._build_result_panel(tab, 7)
        tab.columnconfigure(1, weight=1)
        tab.columnconfigure(3, weight=1)
        tab.rowconfigure(11, weight=1)

        if self.targets:
            first = next((t for t in self.targets if int(t.request.function) in READ_FUNCTIONS), self.targets[0])
            self.target_var.set(first.summary)
            self._target_changed()
        else:
            self.test_button.configure(state="disabled")
            self.status_var.set("This project has no RTU or TCP client requests.")

    def _build_adhoc_tab(self, notebook):
        tab = ttk.Frame(notebook, padding=12)
        notebook.add(tab, text="Ad-hoc Test")
        self.adhoc_device_var = tk.StringVar()
        self.adhoc_function_var = tk.StringVar(value="FC03 Read Holding Registers")
        self.adhoc_register_var = tk.StringVar(value="0")
        self.adhoc_count_var = tk.StringVar(value="1")
        self.adhoc_dtype_var = tk.StringVar(value="int16")
        self.adhoc_order_var = tk.StringVar(value="high_byte_first")
        self.adhoc_status_var = tk.StringVar(value="Choose a configured device and enter a read request.")
        self.adhoc_elapsed_var = tk.StringVar(value="-")
        self.adhoc_value_var = tk.StringVar(value="-")

        labels = [
            ("Target device", self.adhoc_device_var, [t.device_summary for t in self.templates]),
            ("Function", self.adhoc_function_var, list(FUNCTION_CHOICES)),
            ("Register", self.adhoc_register_var, None),
            ("Count", self.adhoc_count_var, None),
            ("Data type", self.adhoc_dtype_var, DATA_TYPES),
            ("Byte order", self.adhoc_order_var, BYTE_ORDERS),
        ]
        for row, (label, variable, choices) in enumerate(labels):
            ttk.Label(tab, text=f"{label}:").grid(row=row, column=0, sticky="w", pady=6)
            if choices is None:
                widget = ttk.Entry(tab, textvariable=variable, width=34)
            else:
                widget = ttk.Combobox(tab, textvariable=variable, values=choices, state="readonly", width=31)
            widget.grid(row=row, column=1, sticky="w", padx=(8, 20), pady=6)
        if self.templates:
            self.adhoc_device_var.set(self.templates[0].device_summary)
        self.adhoc_function_var.trace_add("write", lambda *_args: self._adhoc_function_changed())

        ttk.Button(tab, text="READ", command=self._test_adhoc).grid(row=6, column=0, columnspan=2, pady=(14, 12))
        ttk.Label(tab, text="Status:").grid(row=7, column=0, sticky="nw")
        ttk.Label(tab, textvariable=self.adhoc_status_var, wraplength=650, justify="left").grid(row=7, column=1, sticky="w", padx=(8, 0))
        ttk.Label(tab, text="Response time:").grid(row=8, column=0, sticky="w", pady=5)
        ttk.Label(tab, textvariable=self.adhoc_elapsed_var).grid(row=8, column=1, sticky="w", padx=(8, 0))
        ttk.Label(tab, text="Decoded value:").grid(row=9, column=0, sticky="w", pady=5)
        ttk.Label(tab, textvariable=self.adhoc_value_var).grid(row=9, column=1, sticky="w", padx=(8, 0))
        ttk.Label(tab, text="Raw response:").grid(row=10, column=0, sticky="nw", pady=(5, 0))
        self.adhoc_raw = tk.Text(tab, height=9, wrap="word", font=("Consolas", 9))
        self.adhoc_raw.grid(row=10, column=1, sticky="nsew", padx=(8, 0), pady=(5, 0))
        self.adhoc_raw.configure(state="disabled")
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(10, weight=1)

    def _build_scan_tab(self, notebook):
        tab = ttk.Frame(notebook, padding=12)
        notebook.add(tab, text="Device Scan")
        self.scan_device_var = tk.StringVar()
        self.scan_status_var = tk.StringVar(value="Scan all enabled read requests for one configured device.")
        ttk.Label(tab, text="Device:").grid(row=0, column=0, sticky="w")
        self.scan_device_combo = ttk.Combobox(tab, textvariable=self.scan_device_var, values=[t.device_summary for t in self.templates], state="readonly", width=48)
        self.scan_device_combo.grid(row=0, column=1, sticky="w", padx=(8, 16))
        if self.templates:
            self.scan_device_var.set(self.templates[0].device_summary)
        self.scan_button = ttk.Button(tab, text="SCAN DEVICE", command=self._scan_device)
        self.scan_button.grid(row=0, column=2, padx=4)
        self.stop_button = ttk.Button(tab, text="STOP", command=self._stop_scan, state="disabled")
        self.stop_button.grid(row=0, column=3, padx=4)
        ttk.Label(tab, textvariable=self.scan_status_var, wraplength=760, justify="left").grid(row=1, column=0, columnspan=4, sticky="w", pady=(10, 8))

        columns = ("name", "fc", "register", "count", "value", "time", "status")
        self.scan_tree = ttk.Treeview(tab, columns=columns, show="headings")
        headings = {
            "name": ("Request", 230), "fc": ("FC", 55), "register": ("Register", 75),
            "count": ("Count", 55), "value": ("Value", 150), "time": ("Time ms", 80), "status": ("Status", 230),
        }
        for key, (title, width) in headings.items():
            self.scan_tree.heading(key, text=title)
            self.scan_tree.column(key, width=width, anchor="w")
        y = ttk.Scrollbar(tab, orient="vertical", command=self.scan_tree.yview)
        self.scan_tree.configure(yscrollcommand=y.set)
        self.scan_tree.grid(row=2, column=0, columnspan=4, sticky="nsew")
        y.grid(row=2, column=4, sticky="ns")
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(2, weight=1)

    def _build_write_tab(self, notebook):
        tab = ttk.Frame(notebook, padding=12)
        notebook.add(tab, text="Write Test")
        warning = (
            "DANGER: This sends a real Modbus command to the field device. "
            "Confirm the register and value, make sure the equipment is safe, and use feedback/readback afterward."
        )
        ttk.Label(tab, text=warning, foreground="#b00020", wraplength=820, justify="left", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 12))

        self.write_mode_var = tk.StringVar(value="existing")
        ttk.Radiobutton(tab, text="Existing write request", value="existing", variable=self.write_mode_var, command=self._write_mode_changed).grid(row=1, column=0, sticky="w")
        ttk.Radiobutton(tab, text="Ad-hoc write", value="adhoc", variable=self.write_mode_var, command=self._write_mode_changed).grid(row=1, column=1, sticky="w")

        self.write_existing_var = tk.StringVar()
        ttk.Label(tab, text="Project write request:").grid(row=2, column=0, sticky="w", pady=6)
        self.write_existing_combo = ttk.Combobox(tab, textvariable=self.write_existing_var, values=[target.summary for target in self.write_target_list], state="readonly", width=62)
        self.write_existing_combo.grid(row=2, column=1, columnspan=3, sticky="ew", pady=6)
        self.write_existing_combo.bind("<<ComboboxSelected>>", lambda _event: self._existing_write_changed())
        self.write_existing_values_var = tk.StringVar(value="0")
        ttk.Label(tab, text="Test value(s):").grid(row=3, column=0, sticky="w", pady=6)
        self.write_existing_values_entry = ttk.Entry(tab, textvariable=self.write_existing_values_var, width=34)
        self.write_existing_values_entry.grid(row=3, column=1, sticky="w", pady=6)

        self.write_device_var = tk.StringVar()
        self.write_function_var = tk.StringVar(value="FC06 Write Single Register")
        self.write_register_var = tk.StringVar(value="0")
        self.write_values_var = tk.StringVar(value="0")
        self.write_dtype_var = tk.StringVar(value="int16")
        self.write_order_var = tk.StringVar(value="high_byte_first")
        adhoc_fields = (
            ("Target device", self.write_device_var, [target.device_summary for target in self.templates]),
            ("Function", self.write_function_var, list(WRITE_FUNCTION_CHOICES)),
            ("Register", self.write_register_var, None),
            ("Value(s)", self.write_values_var, None),
            ("Data type", self.write_dtype_var, DATA_TYPES),
            ("Byte order", self.write_order_var, BYTE_ORDERS),
        )
        self.write_adhoc_widgets = []
        for index, (label, variable, choices) in enumerate(adhoc_fields, start=4):
            ttk.Label(tab, text=f"{label}:").grid(row=index, column=0, sticky="w", pady=5)
            widget = ttk.Entry(tab, textvariable=variable, width=34) if choices is None else ttk.Combobox(tab, textvariable=variable, values=choices, state="readonly", width=31)
            widget.grid(row=index, column=1, sticky="w", pady=5)
            self.write_adhoc_widgets.append(widget)
        self.write_function_var.trace_add("write", lambda *_args: self._write_function_changed())

        self.write_status_var = tk.StringVar(value="Select an existing write request or configure an ad-hoc command.")
        self.write_elapsed_var = tk.StringVar(value="-")
        ttk.Button(tab, text="REVIEW AND WRITE", command=self._test_write).grid(row=10, column=0, columnspan=2, pady=(14, 10))
        ttk.Label(tab, text="Status:").grid(row=11, column=0, sticky="nw")
        ttk.Label(tab, textvariable=self.write_status_var, wraplength=680, justify="left").grid(row=11, column=1, columnspan=3, sticky="w")
        ttk.Label(tab, text="Response time:").grid(row=12, column=0, sticky="w", pady=5)
        ttk.Label(tab, textvariable=self.write_elapsed_var).grid(row=12, column=1, sticky="w")
        ttk.Label(tab, text="Raw response:").grid(row=13, column=0, sticky="nw", pady=5)
        self.write_raw = tk.Text(tab, height=7, wrap="word", font=("Consolas", 9))
        self.write_raw.grid(row=13, column=1, columnspan=3, sticky="nsew")
        self.write_raw.configure(state="disabled")
        tab.columnconfigure(1, weight=1)
        tab.columnconfigure(3, weight=1)
        tab.rowconfigure(13, weight=1)
        if self.write_target_list:
            self.write_existing_var.set(self.write_target_list[0].summary)
            self._existing_write_changed()
        if self.templates:
            self.write_device_var.set(self.templates[0].device_summary)
        self._write_mode_changed()

    def _build_result_panel(self, parent, start_row):
        ttk.Label(parent, text="Status:").grid(row=start_row, column=0, sticky="nw")
        ttk.Label(parent, textvariable=self.status_var, wraplength=650, justify="left").grid(row=start_row, column=1, columnspan=3, sticky="w", padx=(8, 0))
        ttk.Label(parent, text="Response time:").grid(row=start_row + 1, column=0, sticky="w", pady=5)
        ttk.Label(parent, textvariable=self.elapsed_var).grid(row=start_row + 1, column=1, sticky="w", padx=(8, 0))
        ttk.Label(parent, text="Decoded value:").grid(row=start_row + 2, column=0, sticky="w", pady=5)
        ttk.Label(parent, textvariable=self.value_var).grid(row=start_row + 2, column=1, columnspan=3, sticky="w", padx=(8, 0))
        ttk.Label(parent, text="Raw response:").grid(row=start_row + 3, column=0, sticky="nw", pady=(5, 0))
        self.raw = tk.Text(parent, height=8, wrap="word", font=("Consolas", 9))
        self.raw.grid(row=start_row + 3, column=1, columnspan=3, sticky="nsew", padx=(8, 0), pady=(5, 0))
        self.raw.configure(state="disabled")

    @staticmethod
    def _set_text(widget: tk.Text, text: str):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

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
            self.status_var.set("Ready for read-only test." if self.execute else "Transport not connected yet.")
        else:
            self.test_button.configure(state="disabled")
            self.status_var.set("Write requests are intentionally disabled in v0.6 live testing.")

    def _test_existing(self):
        target = self._selected_target()
        if target is None or self.execute is None:
            return
        self.status_var.set("Testing...")
        self.elapsed_var.set("-")
        self.value_var.set("-")
        self._set_text(self.raw, "")
        self.update_idletasks()
        result = self.execute(target)
        self.elapsed_var.set(f"{result.elapsed_ms:.1f} ms")
        if result.ok:
            self.status_var.set("OK")
            self.value_var.set(result.value or "-")
            self._set_text(self.raw, result.raw_response)
        else:
            self.status_var.set(f"ERROR: {result.error}")
            self._set_text(self.raw, result.raw_response)

    def _adhoc_function_changed(self):
        function = FUNCTION_CHOICES.get(self.adhoc_function_var.get(), 3)
        if function in {1, 2}:
            self.adhoc_dtype_var.set("bool")
            self.adhoc_order_var.set("none")
        elif self.adhoc_dtype_var.get() == "bool":
            self.adhoc_dtype_var.set("int16")
            self.adhoc_order_var.set("high_byte_first")

    def _test_adhoc(self):
        if self.execute is None:
            return
        template = self.template_by_label.get(self.adhoc_device_var.get())
        if template is None:
            messagebox.showwarning("Live Modbus Tester", "Choose a configured target device.", parent=self)
            return
        try:
            target = make_adhoc_target(
                template,
                function=FUNCTION_CHOICES[self.adhoc_function_var.get()],
                register=int(self.adhoc_register_var.get()),
                count=int(self.adhoc_count_var.get()),
                data_type=self.adhoc_dtype_var.get(),
                byte_order=self.adhoc_order_var.get(),
            )
        except Exception as exc:
            messagebox.showerror("Invalid ad-hoc request", str(exc), parent=self)
            return
        self.adhoc_status_var.set("Testing...")
        self.adhoc_elapsed_var.set("-")
        self.adhoc_value_var.set("-")
        self._set_text(self.adhoc_raw, "")
        self.update_idletasks()
        result = self.execute(target)
        self.adhoc_elapsed_var.set(f"{result.elapsed_ms:.1f} ms")
        if result.ok:
            self.adhoc_status_var.set("OK")
            self.adhoc_value_var.set(result.value or "-")
            self._set_text(self.adhoc_raw, result.raw_response)
        else:
            self.adhoc_status_var.set(f"ERROR: {result.error}")
            self._set_text(self.adhoc_raw, result.raw_response)

    def _write_mode_changed(self):
        existing = self.write_mode_var.get() == "existing"
        self.write_existing_combo.configure(state="readonly" if existing and self.write_target_list else "disabled")
        self.write_existing_values_entry.configure(state="normal" if existing and self.write_target_list else "disabled")
        for widget in self.write_adhoc_widgets:
            widget.configure(state="disabled" if existing else ("readonly" if isinstance(widget, ttk.Combobox) else "normal"))

    def _existing_write_changed(self):
        target = self.write_target_by_label.get(self.write_existing_var.get())
        if target is not None:
            self.write_existing_values_var.set(str(target.request.values or "0"))
            self.write_status_var.set(
                f"Ready: {target.transport.upper()} {target.device_name}, FC{int(target.request.function):02d}, "
                f"register {target.request.register}, value(s) {target.request.values}."
            )

    def _write_function_changed(self):
        function = WRITE_FUNCTION_CHOICES.get(self.write_function_var.get(), 6)
        if function in {5, 15}:
            self.write_dtype_var.set("bool")
            self.write_order_var.set("none")
        elif self.write_dtype_var.get() == "bool":
            self.write_dtype_var.set("int16")
            self.write_order_var.set("high_byte_first")

    def _selected_write_target(self):
        if self.write_mode_var.get() == "existing":
            target = self.write_target_by_label.get(self.write_existing_var.get())
            if target is None:
                raise ValueError("This project has no configured write request to test.")
            return make_adhoc_write_target(
                target,
                function=int(target.request.function),
                register=target.request.register,
                values=self.write_existing_values_var.get(),
                data_type=target.request.data_type,
                byte_order=target.request.byte_order,
            )
        template = self.template_by_label.get(self.write_device_var.get())
        if template is None:
            raise ValueError("Choose a configured target device.")
        return make_adhoc_write_target(
            template,
            function=WRITE_FUNCTION_CHOICES[self.write_function_var.get()],
            register=int(self.write_register_var.get()),
            values=self.write_values_var.get(),
            data_type=self.write_dtype_var.get(),
            byte_order=self.write_order_var.get(),
        )

    def _test_write(self):
        if self.execute is None:
            return
        try:
            target = self._selected_write_target()
        except Exception as exc:
            messagebox.showerror("Invalid write request", str(exc), parent=self)
            return
        request = target.request
        summary = (
            f"Device: {target.transport.upper()} | {target.device_name}\n"
            f"Device/Unit ID: {target.device_id}\n"
            f"Function: FC{int(request.function):02d}\n"
            f"Register: {request.register}\n"
            f"Value(s): {request.values}\n"
            f"Data type / order: {request.data_type} / {request.byte_order}\n\n"
            "This command will be sent immediately. Type WRITE to continue:"
        )
        confirmation = simpledialog.askstring("Confirm live Modbus write", summary, parent=self)
        if confirmation != "WRITE":
            self.write_status_var.set("Write cancelled; confirmation text did not match WRITE.")
            return
        self.write_status_var.set("Writing...")
        self.write_elapsed_var.set("-")
        self._set_text(self.write_raw, "")
        self.update_idletasks()
        result = self.execute(target)
        self.write_elapsed_var.set(f"{result.elapsed_ms:.1f} ms")
        if result.ok:
            self.write_status_var.set("WRITE OK. Verify the value through the normal feedback/readback request.")
            self._set_text(self.write_raw, result.raw_response)
        else:
            self.write_status_var.set(f"WRITE ERROR: {result.error}")
            self._set_text(self.write_raw, result.raw_response)
    def _stop_scan(self):
        self.scan_stop_requested = True

    def _scan_device(self):
        if self.execute is None:
            return
        template = self.template_by_label.get(self.scan_device_var.get())
        if template is None:
            return
        targets = read_targets_for_device(self.targets, template)
        self.scan_tree.delete(*self.scan_tree.get_children())
        if not targets:
            self.scan_status_var.set("No enabled FC01-FC04 requests found for this device.")
            return
        self.scan_stop_requested = False
        self.scan_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        ok_count = 0
        fail_count = 0
        try:
            for index, target in enumerate(targets, start=1):
                if self.scan_stop_requested:
                    self.scan_status_var.set(f"Stopped after {index - 1} of {len(targets)} requests.")
                    break
                self.scan_status_var.set(f"Scanning {index}/{len(targets)}: {target.request.name}")
                self.update()
                result = self.execute(target)
                if result.ok:
                    ok_count += 1
                    status = "OK"
                    value = result.value or "-"
                else:
                    fail_count += 1
                    status = result.error or "ERROR"
                    value = "-"
                self.scan_tree.insert("", "end", values=(
                    target.request.name,
                    f"FC{int(target.request.function):02d}",
                    target.request.register,
                    target.request.count,
                    value,
                    f"{result.elapsed_ms:.1f}",
                    status,
                ))
                self.scan_tree.yview_moveto(1.0)
                self.update()
            else:
                self.scan_status_var.set(f"Scan complete: {ok_count} OK, {fail_count} failed, {len(targets)} total.")
        finally:
            self.scan_button.configure(state="normal")
            self.stop_button.configure(state="disabled")
