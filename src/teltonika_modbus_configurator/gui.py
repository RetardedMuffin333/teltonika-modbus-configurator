"""Tkinter desktop editor built on top of the core project model."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from .deploy import SshSession, read_remote_config
from .loader import load_project
from .models import Device, FunctionCode, Project, Request, SerialConnection, ServerMapping
from .uci_generator import generate_uci
from .uci_parser import import_project
from .validator import validate_project
from .yaml_writer import dump_project


REGISTER_TYPES = ("coil", "discrete_input", "holding_register", "input_register")
PARITIES = ("none", "even", "odd")


class FormDialog(simpledialog.Dialog):
    """Small reusable modal form for primitive project objects."""

    def __init__(self, parent, title: str, fields, initial=None):
        self.fields = fields
        self.initial = initial or {}
        self.values = None
        self.widgets = {}
        super().__init__(parent, title)

    def body(self, master):
        first = None
        for row, field in enumerate(self.fields):
            key, label, kind, choices = field
            ttk.Label(master, text=label).grid(row=row, column=0, sticky="w", padx=6, pady=4)
            value = self.initial.get(key, "")
            if kind == "bool":
                var = tk.BooleanVar(value=bool(value))
                widget = ttk.Checkbutton(master, variable=var)
                widget._tmc_var = var
            elif kind == "choice":
                var = tk.StringVar(value=str(value or choices[0]))
                widget = ttk.Combobox(master, textvariable=var, values=choices, state="readonly")
                widget._tmc_var = var
            else:
                var = tk.StringVar(value=str(value))
                widget = ttk.Entry(master, textvariable=var, width=34)
                widget._tmc_var = var
            widget.grid(row=row, column=1, sticky="ew", padx=6, pady=4)
            if first is None:
                first = widget
        master.columnconfigure(1, weight=1)
        return first

    def validate(self):
        try:
            values = {}
            for key, _label, kind, _choices in self.fields:
                raw = self.widgets[key]._tmc_var.get() if key in self.widgets else None
                values[key] = raw
            self.values = values
            return True
        except Exception as exc:
            messagebox.showerror("Invalid value", str(exc), parent=self)
            return False

    def buttonbox(self):
        box = ttk.Frame(self)
        ttk.Button(box, text="OK", width=10, command=self.ok).pack(side="left", padx=5, pady=5)
        ttk.Button(box, text="Cancel", width=10, command=self.cancel).pack(side="left", padx=5, pady=5)
        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)
        box.pack()

    def body(self, master):  # type: ignore[override]
        first = None
        for row, field in enumerate(self.fields):
            key, label, kind, choices = field
            ttk.Label(master, text=label).grid(row=row, column=0, sticky="w", padx=6, pady=4)
            value = self.initial.get(key, "")
            if kind == "bool":
                var = tk.BooleanVar(value=bool(value))
                widget = ttk.Checkbutton(master, variable=var)
            elif kind == "choice":
                var = tk.StringVar(value=str(value or choices[0]))
                widget = ttk.Combobox(master, textvariable=var, values=choices, state="readonly")
            else:
                var = tk.StringVar(value=str(value))
                widget = ttk.Entry(master, textvariable=var, width=34)
            self.widgets[key] = widget
            widget._tmc_var = var
            widget.grid(row=row, column=1, sticky="ew", padx=6, pady=4)
            if first is None:
                first = widget
        master.columnconfigure(1, weight=1)
        return first


class TextWindow(tk.Toplevel):
    def __init__(self, parent, title: str, text: str):
        super().__init__(parent)
        self.title(title)
        self.geometry("950x700")
        area = tk.Text(self, wrap="none", font=("Consolas", 10))
        y = ttk.Scrollbar(self, orient="vertical", command=area.yview)
        x = ttk.Scrollbar(self, orient="horizontal", command=area.xview)
        area.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        area.grid(row=0, column=0, sticky="nsew")
        y.grid(row=0, column=1, sticky="ns")
        x.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        area.insert("1.0", text)
        area.configure(state="disabled")


class ProjectEditor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Teltonika Modbus Configurator")
        self.geometry("1180x760")
        self.minsize(950, 620)
        self.project = Project()
        self.path: Path | None = None
        self.dirty = False
        self._build_menu()
        self._build_ui()
        self.refresh_all()

    def _build_menu(self):
        menu = tk.Menu(self)
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="New", command=self.new_project)
        file_menu.add_command(label="Open YAML...", command=self.open_yaml)
        file_menu.add_command(label="Import live TRB...", command=self.import_live)
        file_menu.add_separator()
        file_menu.add_command(label="Save", command=self.save)
        file_menu.add_command(label="Save As...", command=self.save_as)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.destroy)
        menu.add_cascade(label="File", menu=file_menu)

        tools = tk.Menu(menu, tearoff=False)
        tools.add_command(label="Validate", command=self.validate_project)
        tools.add_command(label="Preview generated UCI", command=self.preview_uci)
        menu.add_cascade(label="Tools", menu=tools)
        self.config(menu=menu)

    def _build_ui(self):
        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")
        ttk.Label(top, text="Project:").pack(side="left")
        self.project_label = ttk.Label(top, text="<new>")
        self.project_label.pack(side="left", padx=(6, 20))
        ttk.Button(top, text="Validate", command=self.validate_project).pack(side="right", padx=3)
        ttk.Button(top, text="Preview UCI", command=self.preview_uci).pack(side="right", padx=3)
        ttk.Button(top, text="Save", command=self.save).pack(side="right", padx=3)

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._build_connections_tab()
        self._build_devices_tab()
        self._build_mappings_tab()
        self._build_tcp_server_tab()

        self.status = tk.StringVar(value="Ready")
        ttk.Label(self, textvariable=self.status, relief="sunken", anchor="w").pack(fill="x", side="bottom")

    @staticmethod
    def _tree(parent, columns):
        tree = ttk.Treeview(parent, columns=[c[0] for c in columns], show="headings", selectmode="browse")
        for key, title, width in columns:
            tree.heading(key, text=title)
            tree.column(key, width=width, anchor="w")
        return tree

    def _build_connections_tab(self):
        tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(tab, text="Connections")
        self.connections_tree = self._tree(tab, [
            ("name", "Name", 180), ("device", "Device", 160), ("baud", "Baud", 90),
            ("data", "Data", 70), ("parity", "Parity", 90), ("stop", "Stop", 70),
        ])
        self.connections_tree.pack(fill="both", expand=True)
        buttons = ttk.Frame(tab)
        buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(buttons, text="Add", command=self.add_connection).pack(side="left", padx=3)
        ttk.Button(buttons, text="Edit", command=self.edit_connection).pack(side="left", padx=3)
        ttk.Button(buttons, text="Delete", command=self.delete_connection).pack(side="left", padx=3)

    def _build_devices_tab(self):
        tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(tab, text="Devices & Requests")
        pane = ttk.Panedwindow(tab, orient="vertical")
        pane.pack(fill="both", expand=True)
        upper = ttk.Frame(pane)
        lower = ttk.Frame(pane)
        pane.add(upper, weight=3)
        pane.add(lower, weight=2)

        self.devices_tree = self._tree(upper, [
            ("name", "Device", 180), ("slave", "Slave ID", 80), ("conn", "Connection", 150),
            ("period", "Period", 80), ("timeout", "Timeout", 80), ("enabled", "Enabled", 80),
        ])
        self.devices_tree.pack(fill="both", expand=True)
        self.devices_tree.bind("<<TreeviewSelect>>", lambda _e: self.refresh_requests())
        db = ttk.Frame(upper)
        db.pack(fill="x", pady=(6, 4))
        ttk.Button(db, text="Add device", command=self.add_device).pack(side="left", padx=3)
        ttk.Button(db, text="Edit device", command=self.edit_device).pack(side="left", padx=3)
        ttk.Button(db, text="Delete device", command=self.delete_device).pack(side="left", padx=3)

        ttk.Label(lower, text="Requests for selected device").pack(anchor="w")
        self.requests_tree = self._tree(lower, [
            ("name", "Request", 180), ("fc", "FC", 60), ("reg", "Register", 90),
            ("count", "Count", 70), ("dtype", "Data type", 130), ("order", "Byte order", 150),
            ("enabled", "Enabled", 80),
        ])
        self.requests_tree.pack(fill="both", expand=True)
        rb = ttk.Frame(lower)
        rb.pack(fill="x", pady=(6, 0))
        ttk.Button(rb, text="Add request", command=self.add_request).pack(side="left", padx=3)
        ttk.Button(rb, text="Edit request", command=self.edit_request).pack(side="left", padx=3)
        ttk.Button(rb, text="Delete request", command=self.delete_request).pack(side="left", padx=3)

    def _build_mappings_tab(self):
        tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(tab, text="TCP Mappings")
        self.mappings_tree = self._tree(tab, [
            ("name", "Name", 180), ("device", "Source device", 150), ("request", "Request", 150),
            ("type", "TCP type", 140), ("register", "Register", 90), ("enabled", "Enabled", 80),
        ])
        self.mappings_tree.pack(fill="both", expand=True)
        buttons = ttk.Frame(tab)
        buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(buttons, text="Add", command=self.add_mapping).pack(side="left", padx=3)
        ttk.Button(buttons, text="Edit", command=self.edit_mapping).pack(side="left", padx=3)
        ttk.Button(buttons, text="Delete", command=self.delete_mapping).pack(side="left", padx=3)

    def _build_tcp_server_tab(self):
        tab = ttk.Frame(self.tabs, padding=14)
        self.tabs.add(tab, text="TCP Server")
        self.tcp_vars = {
            "port": tk.StringVar(), "device_id": tk.StringVar(),
            "enabled": tk.BooleanVar(), "keep_connection": tk.BooleanVar(),
        }
        ttk.Label(tab, text="Port").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(tab, textvariable=self.tcp_vars["port"], width=15).grid(row=0, column=1, sticky="w")
        ttk.Label(tab, text="Device ID").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(tab, textvariable=self.tcp_vars["device_id"], width=15).grid(row=1, column=1, sticky="w")
        ttk.Checkbutton(tab, text="Enabled", variable=self.tcp_vars["enabled"]).grid(row=2, column=0, columnspan=2, sticky="w", pady=5)
        ttk.Checkbutton(tab, text="Persistent connection", variable=self.tcp_vars["keep_connection"]).grid(row=3, column=0, columnspan=2, sticky="w", pady=5)
        ttk.Button(tab, text="Apply settings to project", command=self.apply_tcp_settings).grid(row=4, column=0, columnspan=2, sticky="w", pady=(12, 0))

    def mark_dirty(self):
        self.dirty = True
        self._update_title()

    def _update_title(self):
        name = str(self.path) if self.path else "<new>"
        self.project_label.configure(text=name)
        self.title(f"Teltonika Modbus Configurator - {name}{' *' if self.dirty else ''}")

    def refresh_all(self):
        self.refresh_connections()
        self.refresh_devices()
        self.refresh_requests()
        self.refresh_mappings()
        ts = self.project.tcp_server
        self.tcp_vars["port"].set(str(ts.port))
        self.tcp_vars["device_id"].set(str(ts.device_id))
        self.tcp_vars["enabled"].set(ts.enabled)
        self.tcp_vars["keep_connection"].set(ts.keep_connection)
        self._update_title()

    @staticmethod
    def _clear(tree):
        tree.delete(*tree.get_children())

    def refresh_connections(self):
        self._clear(self.connections_tree)
        for i, c in enumerate(self.project.connections):
            self.connections_tree.insert("", "end", iid=str(i), values=(c.name, c.device, c.baudrate, c.databits, c.parity, c.stopbits))

    def refresh_devices(self):
        selected = self.devices_tree.selection()
        self._clear(self.devices_tree)
        for i, d in enumerate(self.project.devices):
            self.devices_tree.insert("", "end", iid=str(i), values=(d.name, d.slave_id, d.connection, d.period, d.timeout, "Yes" if d.enabled else "No"))
        if selected and selected[0] in self.devices_tree.get_children():
            self.devices_tree.selection_set(selected[0])

    def selected_device_index(self):
        sel = self.devices_tree.selection()
        return int(sel[0]) if sel else None

    def refresh_requests(self):
        self._clear(self.requests_tree)
        idx = self.selected_device_index()
        if idx is None or idx >= len(self.project.devices):
            return
        for i, r in enumerate(self.project.devices[idx].requests):
            self.requests_tree.insert("", "end", iid=str(i), values=(r.name, int(r.function), r.register, r.count, r.data_type, r.byte_order, "Yes" if r.enabled else "No"))

    def refresh_mappings(self):
        self._clear(self.mappings_tree)
        for i, m in enumerate(self.project.mappings):
            self.mappings_tree.insert("", "end", iid=str(i), values=(m.name, m.device, m.request, m.register_type, m.register, "Yes" if m.enabled else "No"))

    def new_project(self):
        self.project = Project()
        self.path = None
        self.dirty = False
        self.refresh_all()

    def open_yaml(self):
        name = filedialog.askopenfilename(filetypes=[("YAML", "*.yaml *.yml"), ("All files", "*.*")])
        if not name:
            return
        try:
            self.project = load_project(name)
            self.path = Path(name)
            self.dirty = False
            self.refresh_all()
            self.status.set("Loaded project")
        except Exception as exc:
            messagebox.showerror("Open failed", str(exc))

    def import_live(self):
        host = simpledialog.askstring("Import live TRB", "Host/IP:", initialvalue="10.33.22.1", parent=self)
        if not host:
            return
        user = simpledialog.askstring("Import live TRB", "SSH username:", initialvalue="root", parent=self) or "root"
        password = simpledialog.askstring("Import live TRB", "SSH password:", show="*", parent=self)
        if password is None:
            return
        try:
            with SshSession(host, username=user, password=password, trust_new_host=True) as session:
                remote = read_remote_config(session)
            self.project = import_project(remote.modbus_client, remote.modbus_server)
            self.path = None
            self.dirty = True
            self.refresh_all()
            self.status.set(f"Imported live configuration from {host}; save it as YAML before editing")
        except Exception as exc:
            messagebox.showerror("Import failed", str(exc))

    def save(self):
        if self.path is None:
            return self.save_as()
        try:
            self.path.write_text(dump_project(self.project), encoding="utf-8")
            self.dirty = False
            self._update_title()
            self.status.set(f"Saved {self.path}")
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc))

    def save_as(self):
        name = filedialog.asksaveasfilename(defaultextension=".yaml", filetypes=[("YAML", "*.yaml"), ("All files", "*.*")])
        if not name:
            return
        self.path = Path(name)
        self.save()

    def validate_project(self):
        messages = validate_project(self.project)
        if not messages:
            messagebox.showinfo("Validation", "Validation PASS - no errors found.")
            self.status.set("Validation PASS")
            return True
        text = "\n".join(f"{m.level.upper()}: {m.message}" for m in messages)
        TextWindow(self, "Validation results", text)
        self.status.set(f"Validation returned {len(messages)} message(s)")
        return not any(m.level == "error" for m in messages)

    def preview_uci(self):
        try:
            generated = generate_uci(self.project)
            TextWindow(self, "Generated RutOS UCI", "# ===== modbus_client =====\n" + generated.modbus_client + "\n# ===== modbus_server =====\n" + generated.modbus_server)
        except Exception as exc:
            messagebox.showerror("Cannot generate UCI", str(exc))

    def _connection_dialog(self, initial=None):
        dlg = FormDialog(self, "Connection", [
            ("name", "Name", "text", None), ("device", "Device", "text", None),
            ("baudrate", "Baudrate", "text", None), ("databits", "Data bits", "text", None),
            ("parity", "Parity", "choice", PARITIES), ("stopbits", "Stop bits", "text", None),
        ], initial)
        return dlg.values

    def add_connection(self):
        v = self._connection_dialog({"device": "/dev/rs485", "baudrate": 19200, "databits": 8, "parity": "none", "stopbits": 2})
        if not v: return
        self.project.connections.append(SerialConnection(v["name"], v["device"], int(v["baudrate"]), int(v["databits"]), v["parity"], int(v["stopbits"])))
        self.mark_dirty(); self.refresh_all()

    def edit_connection(self):
        sel = self.connections_tree.selection()
        if not sel: return
        i = int(sel[0]); c = self.project.connections[i]
        v = self._connection_dialog(vars_for(c))
        if not v: return
        old_name = c.name
        self.project.connections[i] = SerialConnection(v["name"], v["device"], int(v["baudrate"]), int(v["databits"]), v["parity"], int(v["stopbits"]))
        if old_name != v["name"]:
            for d in self.project.devices:
                if d.connection == old_name: d.connection = v["name"]
        self.mark_dirty(); self.refresh_all()

    def delete_connection(self):
        sel = self.connections_tree.selection()
        if not sel: return
        i = int(sel[0]); name = self.project.connections[i].name
        if any(d.connection == name for d in self.project.devices):
            messagebox.showerror("Cannot delete", "Connection is still used by one or more devices.")
            return
        del self.project.connections[i]; self.mark_dirty(); self.refresh_all()

    def _device_dialog(self, initial=None):
        choices = tuple(c.name for c in self.project.connections) or ("",)
        dlg = FormDialog(self, "Device", [
            ("name", "Name", "text", None), ("slave_id", "Slave ID", "text", None),
            ("connection", "Connection", "choice", choices), ("period", "Period", "text", None),
            ("timeout", "Timeout", "text", None), ("enabled", "Enabled", "bool", None),
        ], initial)
        return dlg.values

    def add_device(self):
        if not self.project.connections:
            messagebox.showerror("No connection", "Create a serial connection first."); return
        v = self._device_dialog({"slave_id": 1, "connection": self.project.connections[0].name, "period": 10, "timeout": 1, "enabled": True})
        if not v: return
        self.project.devices.append(Device(v["name"], int(v["slave_id"]), v["connection"], int(v["period"]), int(v["timeout"]), bool(v["enabled"]), []))
        self.mark_dirty(); self.refresh_all()

    def edit_device(self):
        i = self.selected_device_index()
        if i is None: return
        d = self.project.devices[i]; v = self._device_dialog(vars_for(d))
        if not v: return
        old = d.name
        d.name, d.slave_id, d.connection, d.period, d.timeout, d.enabled = v["name"], int(v["slave_id"]), v["connection"], int(v["period"]), int(v["timeout"]), bool(v["enabled"])
        if old != d.name:
            for m in self.project.mappings:
                if m.device == old: m.device = d.name
        self.mark_dirty(); self.refresh_all()

    def delete_device(self):
        i = self.selected_device_index()
        if i is None: return
        name = self.project.devices[i].name
        if any(m.device == name for m in self.project.mappings):
            messagebox.showerror("Cannot delete", "Device is still referenced by TCP mappings."); return
        del self.project.devices[i]; self.mark_dirty(); self.refresh_all()

    def _request_dialog(self, initial=None):
        dlg = FormDialog(self, "Request", [
            ("name", "Name", "text", None), ("function", "Function code", "choice", ("1", "2", "3", "4")),
            ("register", "First register", "text", None), ("count", "Count", "text", None),
            ("data_type", "Data type", "choice", ("int16",)),
            ("byte_order", "Byte order", "choice", ("high_byte_first", "low_byte_first")),
            ("enabled", "Enabled", "bool", None),
        ], initial)
        return dlg.values

    def add_request(self):
        i = self.selected_device_index()
        if i is None: return
        v = self._request_dialog({"function": "4", "register": 0, "count": 1, "data_type": "int16", "byte_order": "high_byte_first", "enabled": True})
        if not v: return
        self.project.devices[i].requests.append(Request(v["name"], FunctionCode(int(v["function"])), int(v["register"]), int(v["count"]), v["data_type"], v["byte_order"], bool(v["enabled"])))
        self.mark_dirty(); self.refresh_requests()

    def edit_request(self):
        di = self.selected_device_index(); sel = self.requests_tree.selection()
        if di is None or not sel: return
        ri = int(sel[0]); r = self.project.devices[di].requests[ri]
        v = self._request_dialog(vars_for(r) | {"function": str(int(r.function))})
        if not v: return
        old = r.name
        r.name, r.function, r.register, r.count, r.data_type, r.byte_order, r.enabled = v["name"], FunctionCode(int(v["function"])), int(v["register"]), int(v["count"]), v["data_type"], v["byte_order"], bool(v["enabled"])
        if old != r.name:
            for m in self.project.mappings:
                if m.device == self.project.devices[di].name and m.request == old: m.request = r.name
        self.mark_dirty(); self.refresh_all()

    def delete_request(self):
        di = self.selected_device_index(); sel = self.requests_tree.selection()
        if di is None or not sel: return
        ri = int(sel[0]); d = self.project.devices[di]; name = d.requests[ri].name
        if any(m.device == d.name and m.request == name for m in self.project.mappings):
            messagebox.showerror("Cannot delete", "Request is still referenced by TCP mappings."); return
        del d.requests[ri]; self.mark_dirty(); self.refresh_requests()

    def _mapping_dialog(self, initial=None):
        devices = tuple(d.name for d in self.project.devices) or ("",)
        dlg = FormDialog(self, "TCP Mapping", [
            ("name", "Name", "text", None), ("device", "Source device", "choice", devices),
            ("request", "Request name", "text", None), ("register_type", "TCP register type", "choice", REGISTER_TYPES),
            ("register", "TCP register", "text", None), ("enabled", "Enabled", "bool", None),
        ], initial)
        return dlg.values

    def add_mapping(self):
        if not self.project.devices: messagebox.showerror("No devices", "Create a device first."); return
        v = self._mapping_dialog({"device": self.project.devices[0].name, "register_type": "input_register", "register": 1000, "enabled": True})
        if not v: return
        self.project.mappings.append(ServerMapping(v["name"], v["device"], v["request"], int(v["register"]), v["register_type"], bool(v["enabled"])))
        self.mark_dirty(); self.refresh_mappings()

    def edit_mapping(self):
        sel = self.mappings_tree.selection()
        if not sel: return
        i = int(sel[0]); m = self.project.mappings[i]
        v = self._mapping_dialog(vars_for(m))
        if not v: return
        self.project.mappings[i] = ServerMapping(v["name"], v["device"], v["request"], int(v["register"]), v["register_type"], bool(v["enabled"]))
        self.mark_dirty(); self.refresh_mappings()

    def delete_mapping(self):
        sel = self.mappings_tree.selection()
        if not sel: return
        del self.project.mappings[int(sel[0])]; self.mark_dirty(); self.refresh_mappings()

    def apply_tcp_settings(self):
        try:
            self.project.tcp_server.port = int(self.tcp_vars["port"].get())
            self.project.tcp_server.device_id = int(self.tcp_vars["device_id"].get())
            self.project.tcp_server.enabled = bool(self.tcp_vars["enabled"].get())
            self.project.tcp_server.keep_connection = bool(self.tcp_vars["keep_connection"].get())
            self.mark_dirty(); self.status.set("TCP Server settings updated")
        except ValueError as exc:
            messagebox.showerror("Invalid TCP Server setting", str(exc))


def vars_for(obj):
    """Return dataclass slots as a plain mapping without requiring __dict__."""
    return {name: getattr(obj, name) for name in obj.__dataclass_fields__}


def main() -> None:
    ProjectEditor().mainloop()


if __name__ == "__main__":
    main()
