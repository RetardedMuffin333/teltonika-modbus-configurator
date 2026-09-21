"""Guided creation of a first RTU, TCP, or mixed project."""

from __future__ import annotations

from dataclasses import fields
import tkinter as tk
from tkinter import messagebox, ttk

from .first_project import FirstProjectOptions, build_first_project, validate_first_project_options


class FirstProjectWizard(tk.Toplevel):
    PAGE_TITLES = ("Project type", "TCP Server", "Source devices", "Finish")

    def __init__(self, parent):
        super().__init__(parent)
        self.title("First Project Wizard")
        self.geometry("720x590")
        self.minsize(680, 540)
        self.transient(parent)
        self.grab_set()
        self.result = None
        self.page_index = 0
        defaults = FirstProjectOptions()
        self.vars = {}
        for field in fields(defaults):
            value = getattr(defaults, field.name)
            variable = tk.BooleanVar(value=value) if isinstance(value, bool) else tk.StringVar(value=str(value))
            self.vars[field.name] = variable

        header = ttk.Frame(self, padding=(16, 14, 16, 8))
        header.pack(fill="x")
        self.step_label = ttk.Label(header, font=("Segoe UI", 14, "bold"))
        self.step_label.pack(anchor="w")
        self.hint_label = ttk.Label(header, wraplength=670, justify="left")
        self.hint_label.pack(anchor="w", pady=(5, 0))

        self.body = ttk.Frame(self, padding=16)
        self.body.pack(fill="both", expand=True)
        self.pages = [self._type_page(), self._server_page(), self._devices_page(), self._finish_page()]

        footer = ttk.Frame(self, padding=12)
        footer.pack(fill="x", side="bottom")
        ttk.Button(footer, text="Cancel", command=self.destroy).pack(side="right")
        self.next_button = ttk.Button(footer, text="Next >", command=self._next)
        self.next_button.pack(side="right", padx=6)
        self.back_button = ttk.Button(footer, text="< Back", command=self._back)
        self.back_button.pack(side="right")
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self._show_page()
        parent.wait_window(self)

    def _entry(self, parent, row, label, name, *, width=24, choices=None, readonly=False):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=5)
        widget = ttk.Combobox(parent, textvariable=self.vars[name], values=choices, state="readonly" if readonly else "normal", width=width) if choices is not None else ttk.Entry(parent, textvariable=self.vars[name], width=width)
        widget.grid(row=row, column=1, sticky="w", pady=5)

    def _type_page(self):
        page = ttk.Frame(self.body)
        ttk.Label(page, text="What will this Teltonika gateway poll?", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 12))
        choices = (
            ("tcp", "Modbus TCP only", "Ethernet devices such as a Carel controller."),
            ("rtu", "Modbus RTU only", "RS485/RS232 slave devices such as room thermostats."),
            ("mixed", "Mixed RTU + TCP", "Expose both serial and Ethernet devices through one TCP Server."),
        )
        for value, title, description in choices:
            box = ttk.Frame(page)
            box.pack(fill="x", pady=6)
            ttk.Radiobutton(box, text=title, value=value, variable=self.vars["project_type"]).pack(anchor="w")
            ttk.Label(box, text=description, foreground="#555555").pack(anchor="w", padx=(24, 0))
        return page

    def _server_page(self):
        page = ttk.Frame(self.body)
        form = ttk.LabelFrame(page, text="Upstream Modbus TCP Server", padding=14)
        form.pack(fill="x")
        self._entry(form, 0, "Port", "tcp_server_port")
        self._entry(form, 1, "Device ID", "tcp_server_device_id")
        ttk.Checkbutton(form, text="Keep persistent connection", variable=self.vars["keep_connection"]).grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Label(page, text="SCADA/atvise connects to this port and Device ID. Port 502 and Device ID 101 are the tested defaults.", wraplength=640, justify="left").pack(anchor="w", pady=14)
        return page

    def _devices_page(self):
        page = ttk.Frame(self.body)
        self.rtu_frame = ttk.LabelFrame(page, text="First RTU device", padding=10)
        self.rtu_frame.pack(fill="x", pady=(0, 10))
        rtu_fields = (
            ("Connection name", "serial_name", None, False), ("Device path", "serial_device", ("/dev/rs485", "/dev/rs232"), True),
            ("Baudrate", "baudrate", (300, 600, 1200, 2400, 4800, 9600, 14400, 19200, 38400, 57600, 115200), True),
            ("Data bits", "databits", (5, 6, 7, 8), True), ("Parity", "parity", ("none", "even", "odd", "mark", "space"), True),
            ("Stop bits", "stopbits", (1, 2), True), ("Device name", "rtu_device_name", None, False),
            ("Slave ID", "rtu_slave_id", (1, 2, 10, 100, 247), False), ("Period (s)", "rtu_period", (1, 2, 5, 10, 30, 60), False), ("Timeout (s)", "rtu_timeout", (1, 2, 5, 10, 30), False),
        )
        for row, (label, name, choices, readonly) in enumerate(rtu_fields):
            self._entry(self.rtu_frame, row // 2, label, name, width=18, choices=choices, readonly=readonly)
            if row % 2:
                widgets = self.rtu_frame.grid_slaves(row=row // 2)
                widgets[0].grid_configure(column=3)
                widgets[1].grid_configure(column=2, padx=(24, 12))

        self.tcp_frame = ttk.LabelFrame(page, text="First TCP device", padding=10)
        self.tcp_frame.pack(fill="x")
        tcp_fields = (
            ("Device name", "tcp_device_name", None), ("Host / IP", "tcp_host", None),
            ("Port", "tcp_port", (502, 1502)), ("Unit ID", "tcp_unit_id", (0, 1, 2, 10, 101, 247)),
            ("Period (s)", "tcp_period", (1, 2, 5, 10, 30, 60)), ("Timeout (s)", "tcp_timeout", (1, 2, 5, 10, 30)),
        )
        for row, (label, name, choices) in enumerate(tcp_fields):
            self._entry(self.tcp_frame, row // 2, label, name, width=18, choices=choices, readonly=False)
            if row % 2:
                widgets = self.tcp_frame.grid_slaves(row=row // 2)
                widgets[0].grid_configure(column=3)
                widgets[1].grid_configure(column=2, padx=(24, 12))
        return page

    def _finish_page(self):
        page = ttk.Frame(self.body)
        self.summary = tk.Text(page, height=15, wrap="word", font=("Segoe UI", 10), relief="flat", background=self.cget("background"))
        self.summary.pack(fill="both", expand=True)
        next_box = ttk.LabelFrame(page, text="After creating the project", padding=10)
        next_box.pack(fill="x", pady=(10, 0))
        for value, text in (
            ("none", "Continue editing manually"),
            ("register_table", "Open Register Table import"),
            ("symbol_file", "Open atvise Connect Symbol import"),
        ):
            ttk.Radiobutton(next_box, text=text, value=value, variable=self.vars["next_action"]).pack(anchor="w", pady=2)
        return page

    def _collect_options(self):
        try:
            return FirstProjectOptions(
                project_type=self.vars["project_type"].get(),
                tcp_server_port=int(self.vars["tcp_server_port"].get()),
                tcp_server_device_id=int(self.vars["tcp_server_device_id"].get()),
                keep_connection=self.vars["keep_connection"].get(),
                serial_name=self.vars["serial_name"].get(), serial_device=self.vars["serial_device"].get(),
                baudrate=int(self.vars["baudrate"].get()), databits=int(self.vars["databits"].get()),
                parity=self.vars["parity"].get().lower(), stopbits=int(self.vars["stopbits"].get()),
                rtu_device_name=self.vars["rtu_device_name"].get(), rtu_slave_id=int(self.vars["rtu_slave_id"].get()),
                rtu_period=int(self.vars["rtu_period"].get()), rtu_timeout=int(self.vars["rtu_timeout"].get()),
                tcp_device_name=self.vars["tcp_device_name"].get(), tcp_host=self.vars["tcp_host"].get(),
                tcp_port=int(self.vars["tcp_port"].get()), tcp_unit_id=int(self.vars["tcp_unit_id"].get()),
                tcp_period=int(self.vars["tcp_period"].get()), tcp_timeout=int(self.vars["tcp_timeout"].get()),
                next_action=self.vars["next_action"].get(),
            )
        except ValueError:
            raise ValueError("Ports, IDs, periods, timeouts, baudrate, data bits, and stop bits must be whole numbers.")

    def _refresh_summary(self):
        try:
            options = self._collect_options()
            project = build_first_project(options)
            details = [
                f"Project type: {options.project_type.upper()}",
                f"TCP Server: port {project.tcp_server.port}, Device ID {project.tcp_server.device_id}",
                f"Serial connections: {len(project.connections)}",
                f"RTU devices: {len(project.devices)}",
                f"TCP devices: {len(project.tcp_clients)}",
                "", "The project initially contains no requests or mappings.",
                "Add them manually or continue to an import after Finish.",
            ]
            text = "\n".join(details)
        except ValueError as exc:
            text = str(exc)
        self.summary.configure(state="normal")
        self.summary.delete("1.0", "end")
        self.summary.insert("1.0", text)
        self.summary.configure(state="disabled")

    def _show_page(self):
        for page in self.pages:
            page.pack_forget()
        if self.page_index == 2:
            kind = self.vars["project_type"].get()
            if kind in {"rtu", "mixed"}: self.rtu_frame.pack(fill="x", pady=(0, 10))
            else: self.rtu_frame.pack_forget()
            if kind in {"tcp", "mixed"}: self.tcp_frame.pack(fill="x")
            else: self.tcp_frame.pack_forget()
        if self.page_index == 3:
            self._refresh_summary()
        self.pages[self.page_index].pack(fill="both", expand=True)
        self.step_label.configure(text=f"Step {self.page_index + 1} of 4 — {self.PAGE_TITLES[self.page_index]}")
        self.hint_label.configure(text=(
            "Create the minimum valid gateway structure. Requests and mappings can be imported after the wizard."
            if self.page_index < 3 else "Review the project structure before it replaces the current editor project."
        ))
        self.back_button.configure(state="normal" if self.page_index else "disabled")
        self.next_button.configure(text="Finish" if self.page_index == 3 else "Next >")

    def _back(self):
        self.page_index -= 1
        self._show_page()

    def _next(self):
        try:
            options = self._collect_options()
        except ValueError as exc:
            messagebox.showerror("Invalid value", str(exc), parent=self)
            return
        if self.page_index == 3:
            errors = validate_first_project_options(options)
            if errors:
                messagebox.showerror("Cannot create project", "\n".join(errors), parent=self)
                return
            self.result = options, build_first_project(options)
            self.destroy()
            return
        self.page_index += 1
        self._show_page()
