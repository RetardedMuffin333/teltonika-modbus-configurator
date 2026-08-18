"""Tkinter bulk-generation wizard for generic Modbus devices."""

from __future__ import annotations

from dataclasses import asdict
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from .bulk import (
    BulkMappingSpec,
    BulkRequestSpec,
    BulkSpec,
    apply_bulk,
    generate_bulk,
    validate_bulk_spec,
)
from .models import FunctionCode, Project
from .register_allocator import next_free_register


REGISTER_TYPES = ("coil", "discrete_input", "holding_register", "input_register")
BYTE_ORDERS = ("high_byte_first", "low_byte_first")


class RowDialog(simpledialog.Dialog):
    def __init__(self, parent, title, fields, initial=None):
        self.fields = fields
        self.initial = initial or {}
        self.values = None
        self.vars = {}
        super().__init__(parent, title)

    def body(self, master):
        first = None
        for row, (key, label, choices) in enumerate(self.fields):
            ttk.Label(master, text=label).grid(row=row, column=0, sticky="w", padx=6, pady=4)
            value = self.initial.get(key, "")
            if choices is None:
                var = tk.StringVar(value=str(value))
                widget = ttk.Entry(master, textvariable=var, width=34)
            else:
                var = tk.StringVar(value=str(value or choices[0]))
                widget = ttk.Combobox(master, textvariable=var, values=choices, state="readonly", width=31)
            self.vars[key] = var
            widget.grid(row=row, column=1, sticky="ew", padx=6, pady=4)
            first = first or widget
        master.columnconfigure(1, weight=1)
        return first

    def apply(self):
        self.values = {k: v.get() for k, v in self.vars.items()}


class BulkGeneratorWindow(tk.Toplevel):
    def __init__(self, parent, project: Project, on_applied):
        super().__init__(parent)
        self.parent = parent
        self.project = project
        self.on_applied = on_applied
        self.title("Bulk Device Generator")

        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        width = min(1100, max(820, screen_w - 120))
        height = min(760, max(560, screen_h - 140))
        self.geometry(f"{width}x{height}")
        self.minsize(760, 520)

        self.requests: list[BulkRequestSpec] = []
        self.mappings: list[BulkMappingSpec] = []

        self.vars = {
            "template": tk.StringVar(value="<blank>"),
            "connection": tk.StringVar(value=project.connections[0].name if project.connections else ""),
            "name_pattern": tk.StringVar(value="Device{index:02d}"),
            "count": tk.StringVar(value="1"),
            "start_index": tk.StringVar(value="1"),
            "slave_start": tk.StringVar(value="1"),
            "slave_step": tk.StringVar(value="1"),
            "slave_ids": tk.StringVar(value=""),
            "period": tk.StringVar(value="10"),
            "timeout": tk.StringVar(value="1"),
            "enabled": tk.BooleanVar(value=True),
        }

        self._build_ui()
        self._refresh_tables()

    def _build_ui(self):
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)

        # Pack actions first on the bottom so they remain visible even when the
        # center tables have to shrink on smaller/scaled displays.
        actions = ttk.Frame(outer)
        actions.pack(side="bottom", fill="x", pady=(10, 0))
        ttk.Button(actions, text="Preview batch", command=self.preview).pack(side="right", padx=4)
        ttk.Button(actions, text="Add batch to project", command=self.apply_batch).pack(side="right", padx=4)
        ttk.Button(actions, text="Close", command=self.destroy).pack(side="right", padx=4)

        config = ttk.LabelFrame(outer, text="Batch", padding=8)
        config.pack(side="top", fill="x")

        templates = ["<blank>"] + [d.name for d in self.project.devices]
        fields = [
            ("template", "Use existing device as template", templates),
            ("connection", "Connection", [c.name for c in self.project.connections]),
            ("name_pattern", "Device name pattern", None),
            ("count", "Count", None),
            ("start_index", "Start index", None),
            ("slave_start", "Slave ID start", None),
            ("slave_step", "Slave ID step", None),
            ("slave_ids", "Explicit Slave IDs (optional CSV)", None),
            ("period", "Polling period", None),
            ("timeout", "Timeout", None),
        ]

        for row, (key, label, choices) in enumerate(fields):
            ttk.Label(config, text=label).grid(row=row // 2, column=(row % 2) * 2, sticky="w", padx=5, pady=3)
            if choices is None:
                widget = ttk.Entry(config, textvariable=self.vars[key], width=28)
            else:
                widget = ttk.Combobox(config, textvariable=self.vars[key], values=choices, state="readonly", width=25)
            widget.grid(row=row // 2, column=(row % 2) * 2 + 1, sticky="ew", padx=5, pady=3)

        ttk.Checkbutton(config, text="Devices enabled", variable=self.vars["enabled"]).grid(row=5, column=0, sticky="w", padx=5, pady=3)
        ttk.Button(config, text="Load template", command=self.load_template).grid(row=5, column=1, sticky="w", padx=5, pady=3)
        ttk.Label(
            config,
            text="Patterns may use {device}, {index}, {ordinal}, {request}; example: Room{index:02d}",
        ).grid(row=5, column=2, columnspan=2, sticky="w", padx=5, pady=3)
        for col in (1, 3):
            config.columnconfigure(col, weight=1)

        paned = ttk.Panedwindow(outer, orient="vertical")
        paned.pack(side="top", fill="both", expand=True, pady=(10, 0))

        req_frame = ttk.LabelFrame(paned, text="Requests", padding=6)
        map_frame = ttk.LabelFrame(paned, text="TCP Server mappings", padding=6)
        paned.add(req_frame, weight=1)
        paned.add(map_frame, weight=1)

        self.req_tree = ttk.Treeview(
            req_frame,
            columns=("name", "fc", "register", "count", "dtype", "order"),
            show="headings",
            selectmode="browse",
        )
        for key, title, width in (
            ("name", "Name", 170), ("fc", "FC", 55), ("register", "Register", 85),
            ("count", "Count", 65), ("dtype", "Data type", 110), ("order", "Byte order", 150),
        ):
            self.req_tree.heading(key, text=title)
            self.req_tree.column(key, width=width, anchor="w")
        self.req_tree.pack(fill="both", expand=True)
        rb = ttk.Frame(req_frame)
        rb.pack(fill="x", pady=(5, 0))
        ttk.Button(rb, text="Add request", command=self.add_request).pack(side="left", padx=3)
        ttk.Button(rb, text="Edit request", command=self.edit_request).pack(side="left", padx=3)
        ttk.Button(rb, text="Delete request", command=self.delete_request).pack(side="left", padx=3)

        self.map_tree = ttk.Treeview(
            map_frame,
            columns=("name", "request", "type", "start", "step"),
            show="headings",
            selectmode="browse",
        )
        for key, title, width in (
            ("name", "Name pattern", 210), ("request", "Request", 150), ("type", "TCP type", 140),
            ("start", "Start register", 100), ("step", "Step", 70),
        ):
            self.map_tree.heading(key, text=title)
            self.map_tree.column(key, width=width, anchor="w")
        self.map_tree.pack(fill="both", expand=True)
        mb = ttk.Frame(map_frame)
        mb.pack(fill="x", pady=(5, 0))
        ttk.Button(mb, text="Add mapping", command=self.add_mapping).pack(side="left", padx=3)
        ttk.Button(mb, text="Edit mapping", command=self.edit_mapping).pack(side="left", padx=3)
        ttk.Button(mb, text="Delete mapping", command=self.delete_mapping).pack(side="left", padx=3)

    def load_template(self):
        name = self.vars["template"].get()
        if not name or name == "<blank>":
            self.requests = []
            self.mappings = []
            self._refresh_tables()
            return

        device = next((d for d in self.project.devices if d.name == name), None)
        if device is None:
            messagebox.showerror("Template", f"Device {name!r} no longer exists.", parent=self)
            return

        self.vars["connection"].set(device.connection)
        self.vars["period"].set(str(device.period))
        self.vars["timeout"].set(str(device.timeout))
        self.vars["enabled"].set(device.enabled)

        self.requests = [
            BulkRequestSpec(
                name=r.name,
                function=r.function,
                register=r.register,
                count=r.count,
                data_type=r.data_type,
                byte_order=r.byte_order,
                enabled=r.enabled,
            )
            for r in device.requests
        ]

        related = [m for m in self.project.mappings if m.device == device.name]
        self.mappings = [
            BulkMappingSpec(
                name_pattern=self._suggest_mapping_pattern(m.name, device.name, m.request),
                request=m.request,
                register_type=m.register_type,
                start_register=next_free_register(
                    self.project,
                    register_type=m.register_type,
                    request_name=m.request,
                    default=m.register,
                ),
                step=max(1, next((r.count for r in device.requests if r.name == m.request), 1)),
                enabled=m.enabled,
            )
            for m in related
        ]
        self._refresh_tables()

    @staticmethod
    def _suggest_mapping_pattern(name: str, device_name: str, request: str) -> str:
        if device_name in name:
            return name.replace(device_name, "{device}")
        return "{device}_" + (request or "Value")

    def _request_dialog(self, initial=None):
        dlg = RowDialog(self, "Bulk request", [
            ("name", "Name", None),
            ("function", "Function code", ("1", "2", "3", "4")),
            ("register", "First register", None),
            ("count", "Count", None),
            ("data_type", "Data type", ("int16",)),
            ("byte_order", "Byte order", BYTE_ORDERS),
        ], initial or {"function": "4", "register": "0", "count": "1", "data_type": "int16", "byte_order": "high_byte_first"})
        return dlg.values

    def add_request(self):
        v = self._request_dialog()
        if not v:
            return
        try:
            self.requests.append(BulkRequestSpec(v["name"], FunctionCode(int(v["function"])), int(v["register"]), int(v["count"]), v["data_type"], v["byte_order"], True))
            self._refresh_tables()
        except Exception as exc:
            messagebox.showerror("Request", str(exc), parent=self)

    def edit_request(self):
        sel = self.req_tree.selection()
        if not sel:
            return
        i = int(sel[0])
        r = self.requests[i]
        v = self._request_dialog({**asdict(r), "function": str(int(r.function))})
        if not v:
            return
        try:
            old = r.name
            self.requests[i] = BulkRequestSpec(v["name"], FunctionCode(int(v["function"])), int(v["register"]), int(v["count"]), v["data_type"], v["byte_order"], r.enabled)
            if old != v["name"]:
                for m in self.mappings:
                    if m.request == old:
                        m.request = v["name"]
            self._refresh_tables()
        except Exception as exc:
            messagebox.showerror("Request", str(exc), parent=self)

    def delete_request(self):
        sel = self.req_tree.selection()
        if not sel:
            return
        i = int(sel[0])
        name = self.requests[i].name
        if any(m.request == name for m in self.mappings):
            messagebox.showerror("Request", "Delete or change mappings that reference this request first.", parent=self)
            return
        del self.requests[i]
        self._refresh_tables()

    def _mapping_dialog(self, initial=None):
        requests = tuple(r.name for r in self.requests) or ("",)
        dlg = RowDialog(self, "Bulk TCP mapping", [
            ("name_pattern", "Name pattern", None),
            ("request", "Source request", requests),
            ("register_type", "TCP register type", REGISTER_TYPES),
            ("start_register", "Start register", None),
            ("step", "Step per device", None),
        ], initial or {"name_pattern": "{device}_{request}", "request": requests[0], "register_type": "input_register", "start_register": "1000", "step": "1"})
        return dlg.values

    def add_mapping(self):
        if not self.requests:
            messagebox.showerror("Mapping", "Add at least one request first.", parent=self)
            return
        v = self._mapping_dialog()
        if not v:
            return
        try:
            self.mappings.append(BulkMappingSpec(v["name_pattern"], v["request"], v["register_type"], int(v["start_register"]), int(v["step"]), True))
            self._refresh_tables()
        except Exception as exc:
            messagebox.showerror("Mapping", str(exc), parent=self)

    def edit_mapping(self):
        sel = self.map_tree.selection()
        if not sel:
            return
        i = int(sel[0])
        m = self.mappings[i]
        v = self._mapping_dialog(asdict(m))
        if not v:
            return
        try:
            self.mappings[i] = BulkMappingSpec(v["name_pattern"], v["request"], v["register_type"], int(v["start_register"]), int(v["step"]), m.enabled)
            self._refresh_tables()
        except Exception as exc:
            messagebox.showerror("Mapping", str(exc), parent=self)

    def delete_mapping(self):
        sel = self.map_tree.selection()
        if not sel:
            return
        del self.mappings[int(sel[0])]
        self._refresh_tables()

    def _refresh_tables(self):
        self.req_tree.delete(*self.req_tree.get_children())
        for i, r in enumerate(self.requests):
            self.req_tree.insert("", "end", iid=str(i), values=(r.name, int(r.function), r.register, r.count, r.data_type, r.byte_order))
        self.map_tree.delete(*self.map_tree.get_children())
        for i, m in enumerate(self.mappings):
            self.map_tree.insert("", "end", iid=str(i), values=(m.name_pattern, m.request, m.register_type, m.start_register, m.step))

    def _spec(self) -> BulkSpec:
        explicit = self.vars["slave_ids"].get().strip()
        slave_ids = None
        if explicit:
            slave_ids = [int(x.strip()) for x in explicit.split(",") if x.strip()]
        return BulkSpec(
            connection=self.vars["connection"].get(),
            name_pattern=self.vars["name_pattern"].get().strip(),
            count=int(self.vars["count"].get()),
            start_index=int(self.vars["start_index"].get()),
            slave_start=int(self.vars["slave_start"].get()),
            slave_step=int(self.vars["slave_step"].get()),
            slave_ids=slave_ids,
            period=int(self.vars["period"].get()),
            timeout=int(self.vars["timeout"].get()),
            enabled=bool(self.vars["enabled"].get()),
            requests=list(self.requests),
            mappings=list(self.mappings),
        )

    def preview(self):
        try:
            spec = self._spec()
            errors = validate_bulk_spec(self.project, spec)
            if errors:
                raise ValueError("\n".join(errors))
            result = generate_bulk(self.project, spec)
            lines = [f"Devices: {len(result.devices)}", f"TCP mappings: {len(result.mappings)}", ""]
            for d in result.devices:
                lines.append(f"{d.name}: Slave {d.slave_id} on {d.connection}")
                for r in d.requests:
                    lines.append(f"  {r.name}: FC{int(r.function):02d} register {r.register} count {r.count}")
            lines.append("")
            lines.append("TCP mappings:")
            for m in result.mappings:
                lines.append(f"  {m.name}: {m.device}/{m.request} -> {m.register_type} {m.register}")
            self._show_text("Bulk preview", "\n".join(lines))
        except Exception as exc:
            messagebox.showerror("Bulk preview", str(exc), parent=self)

    def apply_batch(self):
        try:
            spec = self._spec()
            result = generate_bulk(self.project, spec)
            if not messagebox.askyesno(
                "Add batch",
                f"Add {len(result.devices)} devices and {len(result.mappings)} TCP mappings to the project?\n\nThis does NOT write to the TRB yet.",
                parent=self,
            ):
                return
            apply_bulk(self.project, spec)
            self.on_applied()
            messagebox.showinfo("Bulk generator", "Batch added to the project. Review, validate, save, and preview the live diff before deployment.", parent=self)
            self.destroy()
        except Exception as exc:
            messagebox.showerror("Bulk generator", str(exc), parent=self)

    def _show_text(self, title: str, text: str):
        window = tk.Toplevel(self)
        window.title(title)
        window.geometry("900x650")
        area = tk.Text(window, wrap="none", font=("Consolas", 10))
        y = ttk.Scrollbar(window, orient="vertical", command=area.yview)
        x = ttk.Scrollbar(window, orient="horizontal", command=area.xview)
        area.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        area.grid(row=0, column=0, sticky="nsew")
        y.grid(row=0, column=1, sticky="ns")
        x.grid(row=1, column=0, sticky="ew")
        window.rowconfigure(0, weight=1)
        window.columnconfigure(0, weight=1)
        area.insert("1.0", text)
        area.configure(state="disabled")
