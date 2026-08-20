"""Tkinter bulk-generation wizard for RTU and Modbus TCP Client devices."""

from __future__ import annotations

from dataclasses import asdict
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from .bulk import (
    BYTE_ORDERS_BY_TYPE,
    BulkMappingSpec,
    BulkRequestSpec,
    BulkSpec,
    apply_bulk,
    generate_bulk,
    suggested_register_type,
    validate_bulk_spec,
)
from .models import FunctionCode, Project, permissions_for_function
from .register_allocator import next_free_register

REGISTER_TYPES = ("coil", "discrete_input", "holding_register", "input_register")
REQUEST_DATA_TYPES = ("int8", "uint8", "int16", "uint16", "int32", "uint32", "float32", "ascii", "hex", "bool", "pdu")
TCP_DATA_TYPES = ("binary", "string", "bool", "int8", "uint8", "int16", "uint16", "int32", "uint32", "float32")
FUNCTIONS = ("1", "2", "3", "4", "5", "6", "15", "16")
TRANSPORTS = ("rtu", "tcp")


class RowDialog(simpledialog.Dialog):
    def __init__(self, parent, title, fields, initial=None):
        self.fields = fields
        self.initial = initial or {}
        self.values = None
        self.vars = {}
        self.widgets = {}
        super().__init__(parent, title)

    def body(self, master):
        first = None
        for row, (key, label, choices) in enumerate(self.fields):
            ttk.Label(master, text=label).grid(row=row, column=0, sticky="w", padx=6, pady=4)
            value = self.initial.get(key, "")
            if choices is None:
                var = tk.StringVar(value=str(value)); widget = ttk.Entry(master, textvariable=var, width=34)
            else:
                var = tk.StringVar(value=str(value or choices[0])); widget = ttk.Combobox(master, textvariable=var, values=choices, state="readonly", width=31)
            self.vars[key] = var; self.widgets[key] = widget
            widget.grid(row=row, column=1, sticky="ew", padx=6, pady=4); first = first or widget
        master.columnconfigure(1, weight=1)
        return first

    def apply(self):
        self.values = {k: v.get() for k, v in self.vars.items()}


class SmartRequestDialog(RowDialog):
    def body(self, master):
        first = super().body(master)
        self.widgets["data_type"].bind("<<ComboboxSelected>>", self._sync_byte_orders)
        self._sync_byte_orders()
        return first

    def _sync_byte_orders(self, _event=None):
        dtype = self.vars["data_type"].get()
        allowed = tuple(sorted(BYTE_ORDERS_BY_TYPE.get(dtype, {"none"})))
        self.widgets["byte_order"].configure(values=allowed)
        if self.vars["byte_order"].get() not in allowed:
            self.vars["byte_order"].set(allowed[0])


class BulkGeneratorWindow(tk.Toplevel):
    def __init__(self, parent, project: Project, on_applied):
        super().__init__(parent)
        self.parent = parent; self.project = project; self.on_applied = on_applied
        self.title("Bulk Device Generator")
        screen_w = self.winfo_screenwidth(); screen_h = self.winfo_screenheight()
        width = min(1220, max(900, screen_w - 100)); height = min(850, max(600, screen_h - 120))
        self.geometry(f"{width}x{height}"); self.minsize(850, 560)
        self.requests: list[BulkRequestSpec] = []
        self.mappings: list[BulkMappingSpec] = []
        self.template_lookup: dict[str, tuple[str, object]] = {}
        for d in project.devices: self.template_lookup[f"[RTU] {d.name}"] = ("rtu", d)
        for d in project.tcp_clients: self.template_lookup[f"[TCP] {d.name}"] = ("tcp", d)
        self.vars = {
            "template": tk.StringVar(value="<blank>"), "transport": tk.StringVar(value="rtu"),
            "connection": tk.StringVar(value=project.connections[0].name if project.connections else ""),
            "host": tk.StringVar(value=""), "port": tk.StringVar(value="502"),
            "name_pattern": tk.StringVar(value="Device{index:02d}"), "count": tk.StringVar(value="1"),
            "start_index": tk.StringVar(value="1"), "slave_start": tk.StringVar(value="1"),
            "slave_step": tk.StringVar(value="1"), "slave_ids": tk.StringVar(value=""),
            "period": tk.StringVar(value="10"), "timeout": tk.StringVar(value="1"),
            "enabled": tk.BooleanVar(value=True),
        }
        self._build_ui(); self._refresh_tables()

    def _build_ui(self):
        outer = ttk.Frame(self, padding=10); outer.pack(fill="both", expand=True)
        actions = ttk.Frame(outer); actions.pack(side="bottom", fill="x", pady=(10, 0))
        ttk.Button(actions, text="Preview batch", command=self.preview).pack(side="right", padx=4)
        ttk.Button(actions, text="Add batch to project", command=self.apply_batch).pack(side="right", padx=4)
        ttk.Button(actions, text="Close", command=self.destroy).pack(side="right", padx=4)

        config = ttk.LabelFrame(outer, text="Batch", padding=8); config.pack(side="top", fill="x")
        templates = ["<blank>"] + list(self.template_lookup)
        fields = [
            ("template", "Use existing device as template", templates), ("transport", "Transport", TRANSPORTS),
            ("connection", "RTU connection", [c.name for c in self.project.connections] or [""]), ("host", "TCP Host / IP", None),
            ("port", "TCP port", None), ("name_pattern", "Device name pattern", None),
            ("count", "Count", None), ("start_index", "Start index", None),
            ("slave_start", "Slave / Unit ID start", None), ("slave_step", "Slave / Unit ID step", None),
            ("slave_ids", "Explicit Slave / Unit IDs (CSV)", None), ("period", "Polling period", None),
            ("timeout", "Timeout", None),
        ]
        for row, (key, label, choices) in enumerate(fields):
            r, pair = divmod(row, 2); c = pair * 2
            ttk.Label(config, text=label).grid(row=r, column=c, sticky="w", padx=5, pady=3)
            widget = ttk.Entry(config, textvariable=self.vars[key], width=28) if choices is None else ttk.Combobox(config, textvariable=self.vars[key], values=choices, state="readonly", width=25)
            widget.grid(row=r, column=c + 1, sticky="ew", padx=5, pady=3)
        ttk.Checkbutton(config, text="Devices enabled", variable=self.vars["enabled"]).grid(row=7, column=0, sticky="w", padx=5, pady=3)
        ttk.Button(config, text="Load template", command=self.load_template).grid(row=7, column=1, sticky="w", padx=5, pady=3)
        ttk.Label(config, text="Patterns may use {device}, {index}, {ordinal}, {request}").grid(row=7, column=2, columnspan=2, sticky="w", padx=5, pady=3)
        for col in (1, 3): config.columnconfigure(col, weight=1)

        paned = ttk.Panedwindow(outer, orient="vertical"); paned.pack(side="top", fill="both", expand=True, pady=(10, 0))
        req_frame = ttk.LabelFrame(paned, text="Requests", padding=6); map_frame = ttk.LabelFrame(paned, text="TCP Server mappings", padding=6)
        paned.add(req_frame, weight=1); paned.add(map_frame, weight=1)

        self.req_tree = ttk.Treeview(req_frame, columns=("name", "fc", "register", "count", "dtype", "order"), show="headings", selectmode="browse")
        for key, title, width in (("name", "Name", 160), ("fc", "FC", 50), ("register", "Register", 75), ("count", "Count / Values", 110), ("dtype", "Data type", 100), ("order", "Byte order", 130)):
            self.req_tree.heading(key, text=title); self.req_tree.column(key, width=width, anchor="w")
        self.req_tree.pack(fill="both", expand=True)
        rb = ttk.Frame(req_frame); rb.pack(fill="x", pady=(5, 0))
        ttk.Button(rb, text="Add request", command=self.add_request).pack(side="left", padx=3)
        ttk.Button(rb, text="Edit request", command=self.edit_request).pack(side="left", padx=3)
        ttk.Button(rb, text="Delete request", command=self.delete_request).pack(side="left", padx=3)

        self.map_tree = ttk.Treeview(map_frame, columns=("name", "request", "type", "start", "step", "access", "dtype", "count"), show="headings", selectmode="browse")
        for key, title, width in (("name", "Name pattern", 190), ("request", "Request", 120), ("type", "TCP type", 115), ("start", "Start", 70), ("step", "Step", 55), ("access", "Access (auto)", 80), ("dtype", "Data type", 80), ("count", "Count", 55)):
            self.map_tree.heading(key, text=title); self.map_tree.column(key, width=width, anchor="w")
        self.map_tree.pack(fill="both", expand=True)
        mb = ttk.Frame(map_frame); mb.pack(fill="x", pady=(5, 0))
        ttk.Button(mb, text="Add mapping", command=self.add_mapping).pack(side="left", padx=3)
        ttk.Button(mb, text="Edit mapping", command=self.edit_mapping).pack(side="left", padx=3)
        ttk.Button(mb, text="Delete mapping", command=self.delete_mapping).pack(side="left", padx=3)

    def load_template(self):
        selected = self.vars["template"].get()
        if not selected or selected == "<blank>":
            self.requests = []; self.mappings = []; self._refresh_tables(); return
        item = self.template_lookup.get(selected)
        if item is None:
            messagebox.showerror("Template", f"Template {selected!r} no longer exists.", parent=self); return
        transport, device = item
        self.vars["transport"].set(transport)
        self.vars["period"].set(str(device.period)); self.vars["timeout"].set(str(device.timeout)); self.vars["enabled"].set(device.enabled)
        self.vars["name_pattern"].set(device.name + "_{index:02d}")
        if transport == "rtu":
            self.vars["connection"].set(device.connection); self.vars["slave_start"].set(str(device.slave_id))
        else:
            self.vars["host"].set(device.host); self.vars["port"].set(str(device.port)); self.vars["slave_start"].set(str(device.server_id))
        self.requests = [BulkRequestSpec(name=r.name, function=r.function, register=r.register, count=r.count, data_type=r.data_type,
                                         byte_order=r.byte_order, enabled=r.enabled, values=r.values, raw_data_type=r.raw_data_type)
                         for r in device.requests]
        related = [m for m in self.project.mappings if m.device == device.name]
        self.mappings = [BulkMappingSpec(name_pattern=self._suggest_mapping_pattern(m.name, device.name, m.request), request=m.request,
                                         register_type=m.register_type,
                                         start_register=next_free_register(self.project, register_type=m.register_type, request_name=m.request, default=m.register),
                                         step=max(1, m.count), enabled=m.enabled, data_type=m.data_type, count=m.count)
                         for m in related]
        self._refresh_tables()

    @staticmethod
    def _suggest_mapping_pattern(name: str, device_name: str, request: str) -> str:
        return name.replace(device_name, "{device}") if device_name in name else "{device}_" + (request or "Value")

    def _request_dialog(self, initial=None):
        initial = initial or {"function": "4", "register": "0", "count": "1", "values": "", "data_type": "int16", "byte_order": "high_byte_first"}
        dlg = SmartRequestDialog(self, "Bulk request", [
            ("name", "Name", None), ("function", "Function code", FUNCTIONS), ("register", "First register", None),
            ("count", "Read count", None), ("values", "Write value(s)", None), ("data_type", "Data type", REQUEST_DATA_TYPES),
            ("byte_order", "Byte order", tuple(sorted({x for values in BYTE_ORDERS_BY_TYPE.values() for x in values}))),
        ], initial)
        return dlg.values

    def add_request(self):
        v = self._request_dialog()
        if not v: return
        try:
            self.requests.append(BulkRequestSpec(name=v["name"], function=FunctionCode(int(v["function"])), register=int(v["register"]),
                                                 count=int(v["count"] or 1), data_type=v["data_type"], byte_order=v["byte_order"], values=v["values"].strip() or None))
            self._refresh_tables()
        except Exception as exc: messagebox.showerror("Request", str(exc), parent=self)

    def edit_request(self):
        sel = self.req_tree.selection()
        if not sel: return
        i = int(sel[0]); r = self.requests[i]
        if r.raw_data_type:
            messagebox.showerror("Request", "Raw imported RutOS datatype is preserved but not editable yet.", parent=self); return
        initial = asdict(r); initial["function"] = str(int(r.function)); initial["values"] = r.values or ""
        v = self._request_dialog(initial)
        if not v: return
        try:
            old = r.name
            self.requests[i] = BulkRequestSpec(name=v["name"], function=FunctionCode(int(v["function"])), register=int(v["register"]),
                                               count=int(v["count"] or 1), data_type=v["data_type"], byte_order=v["byte_order"], enabled=r.enabled,
                                               values=v["values"].strip() or None)
            if old != v["name"]:
                for m in self.mappings:
                    if m.request == old: m.request = v["name"]
            self._refresh_tables()
        except Exception as exc: messagebox.showerror("Request", str(exc), parent=self)

    def delete_request(self):
        sel = self.req_tree.selection()
        if not sel: return
        i = int(sel[0]); name = self.requests[i].name
        if any(m.request == name for m in self.mappings):
            messagebox.showerror("Request", "Delete or change mappings that reference this request first.", parent=self); return
        del self.requests[i]; self._refresh_tables()

    def _request_named(self, request_name: str) -> BulkRequestSpec:
        request = next((r for r in self.requests if r.name == request_name), None)
        if request is None: raise ValueError(f"Unknown source request {request_name!r}")
        return request

    def _access_for_request(self, request_name: str) -> str:
        return permissions_for_function(self._request_named(request_name).function)

    @staticmethod
    def _tcp_dtype_for_request(request: BulkRequestSpec) -> str:
        if request.function in {FunctionCode.READ_COILS, FunctionCode.READ_DISCRETE_INPUTS, FunctionCode.WRITE_SINGLE_COIL, FunctionCode.WRITE_MULTIPLE_COILS}:
            return "bool"
        return request.data_type if request.data_type in TCP_DATA_TYPES else "int16"

    def _mapping_dialog(self, initial=None):
        requests = tuple(r.name for r in self.requests) or ("",)
        if initial is None:
            request = self.requests[0] if self.requests else None
            register_type = suggested_register_type(request.function) if request else "input_register"
            dtype = self._tcp_dtype_for_request(request) if request else "int16"
            start = next_free_register(self.project, register_type=register_type, request_name=request.name if request else "", default=1025)
            initial = {"name_pattern": "{device}_{request}", "request": requests[0], "register_type": register_type,
                       "start_register": str(start), "step": "1", "data_type": dtype, "count": "1"}
        dlg = RowDialog(self, "Bulk TCP mapping", [
            ("name_pattern", "Name pattern", None), ("request", "Source request", requests),
            ("register_type", "TCP register type", REGISTER_TYPES), ("start_register", "Start register", None),
            ("step", "Step per device", None), ("data_type", "Register data type", TCP_DATA_TYPES), ("count", "Value count", None),
        ], initial)
        return dlg.values

    def add_mapping(self):
        if not self.requests:
            messagebox.showerror("Mapping", "Add at least one request first.", parent=self); return
        v = self._mapping_dialog()
        if not v: return
        try:
            request = self._request_named(v["request"]); natural_type = suggested_register_type(request.function)
            if v["register_type"] != natural_type:
                raise ValueError(f"FC{int(request.function):02d} maps to TCP {natural_type}, not {v['register_type']}.")
            self.mappings.append(BulkMappingSpec(name_pattern=v["name_pattern"], request=v["request"], register_type=v["register_type"],
                                                 start_register=int(v["start_register"]), step=int(v["step"]),
                                                 permissions=self._access_for_request(v["request"]), data_type=v["data_type"], count=int(v["count"] or 1)))
            self._refresh_tables()
        except Exception as exc: messagebox.showerror("Mapping", str(exc), parent=self)

    def edit_mapping(self):
        sel = self.map_tree.selection()
        if not sel: return
        i = int(sel[0]); m = self.mappings[i]; initial = asdict(m); initial["count"] = m.count or 1
        v = self._mapping_dialog(initial)
        if not v: return
        try:
            request = self._request_named(v["request"]); natural_type = suggested_register_type(request.function)
            if v["register_type"] != natural_type:
                raise ValueError(f"FC{int(request.function):02d} maps to TCP {natural_type}, not {v['register_type']}.")
            self.mappings[i] = BulkMappingSpec(name_pattern=v["name_pattern"], request=v["request"], register_type=v["register_type"],
                                               start_register=int(v["start_register"]), step=int(v["step"]), enabled=m.enabled,
                                               permissions=self._access_for_request(v["request"]), data_type=v["data_type"], count=int(v["count"] or 1))
            self._refresh_tables()
        except Exception as exc: messagebox.showerror("Mapping", str(exc), parent=self)

    def delete_mapping(self):
        sel = self.map_tree.selection()
        if not sel: return
        del self.mappings[int(sel[0])]; self._refresh_tables()

    def _refresh_tables(self):
        self.req_tree.delete(*self.req_tree.get_children())
        for i, r in enumerate(self.requests):
            self.req_tree.insert("", "end", iid=str(i), values=(r.name, int(r.function), r.register,
                                 r.values if r.function.is_write else r.count, r.raw_data_type or r.data_type, r.byte_order))
        self.map_tree.delete(*self.map_tree.get_children())
        for i, m in enumerate(self.mappings):
            self.map_tree.insert("", "end", iid=str(i), values=(m.name_pattern, m.request, m.register_type, m.start_register,
                                 m.step, self._access_for_request(m.request), m.data_type, m.count or 1))

    def _spec(self) -> BulkSpec:
        explicit = self.vars["slave_ids"].get().strip()
        ids = [int(x.strip()) for x in explicit.split(",") if x.strip()] if explicit else None
        return BulkSpec(
            transport=self.vars["transport"].get(), connection=self.vars["connection"].get(), host=self.vars["host"].get().strip(),
            port=int(self.vars["port"].get()), name_pattern=self.vars["name_pattern"].get().strip(), count=int(self.vars["count"].get()),
            start_index=int(self.vars["start_index"].get()), slave_start=int(self.vars["slave_start"].get()),
            slave_step=int(self.vars["slave_step"].get()), slave_ids=ids, period=int(self.vars["period"].get()),
            timeout=int(self.vars["timeout"].get()), enabled=bool(self.vars["enabled"].get()),
            requests=list(self.requests), mappings=list(self.mappings),
        )

    def preview(self):
        try:
            spec = self._spec(); errors = validate_bulk_spec(self.project, spec)
            if errors: raise ValueError("\n".join(errors))
            result = generate_bulk(self.project, spec)
            lines = [f"RTU devices: {len(result.devices)}", f"TCP clients: {len(result.tcp_clients)}", f"TCP mappings: {len(result.mappings)}", ""]
            for d in result.devices:
                lines.append(f"{d.name}: RTU Slave {d.slave_id} on {d.connection}")
                for r in d.requests: lines.append(self._preview_request(r))
            for d in result.tcp_clients:
                lines.append(f"{d.name}: TCP {d.host}:{d.port}, Unit ID {d.server_id}")
                for r in d.requests: lines.append(self._preview_request(r))
            lines.append(""); lines.append("TCP mappings:")
            for m in result.mappings:
                lines.append(f"  {m.name}: {m.device}/{m.request} -> {m.register_type} {m.register} [{m.permissions}, {m.data_type}]")
            self._show_text("Bulk preview", "\n".join(lines))
        except Exception as exc: messagebox.showerror("Bulk preview", str(exc), parent=self)

    @staticmethod
    def _preview_request(r):
        detail = "values " + str(r.values) if r.function.is_write else "count " + str(r.count)
        return f"  {r.name}: FC{int(r.function):02d} register {r.register} {detail} [{r.data_type}/{r.byte_order}]"

    def apply_batch(self):
        try:
            spec = self._spec(); result = generate_bulk(self.project, spec)
            total = len(result.devices) + len(result.tcp_clients)
            if not messagebox.askyesno("Add batch", f"Add {total} devices and {len(result.mappings)} TCP mappings to the project?\n\nThis does NOT write to the TRB yet.", parent=self): return
            apply_bulk(self.project, spec); self.on_applied()
            messagebox.showinfo("Bulk generator", "Batch added to the project. Review, validate, save, and preview the live diff before deployment.", parent=self)
            self.destroy()
        except Exception as exc: messagebox.showerror("Bulk generator", str(exc), parent=self)

    def _show_text(self, title: str, text: str):
        window = tk.Toplevel(self); window.title(title); window.geometry("900x650")
        area = tk.Text(window, wrap="none", font=("Consolas", 10))
        y = ttk.Scrollbar(window, orient="vertical", command=area.yview); x = ttk.Scrollbar(window, orient="horizontal", command=area.xview)
        area.configure(yscrollcommand=y.set, xscrollcommand=x.set); area.grid(row=0, column=0, sticky="nsew")
        y.grid(row=0, column=1, sticky="ns"); x.grid(row=1, column=0, sticky="ew")
        window.rowconfigure(0, weight=1); window.columnconfigure(0, weight=1)
        area.insert("1.0", text); area.configure(state="disabled")
