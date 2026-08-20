"""Extended desktop entry point with deployment, bulk, export, and v0.3 Modbus tools."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .atvise_symbols import export_atvise_symbols
from .gui import FormDialog, vars_for
from .gui_bulk import BulkGeneratorWindow
from .gui_deploy import DeploymentEditor
from .models import FunctionCode, Request, ServerMapping, TcpClientDevice, permissions_for_function

FUNCTION_CHOICES = (
    "1 - Read coils", "2 - Read discrete inputs", "3 - Read holding registers", "4 - Read input registers",
    "5 - Set single coil", "6 - Set single holding register", "15 - Set multiple coils", "16 - Set multiple holding registers",
)
REQUEST_DATA_TYPES = ("int8", "uint8", "int16", "uint16", "int32", "uint32", "float32", "ascii", "hex", "bool", "pdu")
BYTE_ORDERS = ("none", "high_byte_first", "low_byte_first", "1234", "2143", "3412", "4321")
TCP_DATA_TYPES = ("binary", "string", "bool", "int8", "uint8", "int16", "uint16", "int32", "uint32", "int64", "uint64", "float32", "float64")
REGISTER_TYPES = ("coil", "discrete_input", "holding_register", "input_register")


def _fc_text(value: int | FunctionCode) -> str:
    prefix = f"{int(value)} - "
    return next((item for item in FUNCTION_CHOICES if item.startswith(prefix)), str(int(value)))


def _parse_fc(value: str) -> FunctionCode:
    return FunctionCode(int(value.split("-", 1)[0].strip()))


class ExtendedProjectEditor(DeploymentEditor):
    def _build_menu(self):
        super()._build_menu()
        menu = self.nametowidget(self.cget("menu"))
        bulk_menu = tk.Menu(menu, tearoff=False)
        bulk_menu.add_command(label="Bulk Device Generator...", command=self.open_bulk_generator)
        menu.add_cascade(label="Bulk", menu=bulk_menu)
        export_menu = tk.Menu(menu, tearoff=False)
        export_menu.add_command(label="atvise Connect Symbol file (all mappings)...", command=lambda: self.export_atvise_symbol_file(include_disabled=True))
        export_menu.add_command(label="atvise Connect Symbol file (enabled only)...", command=lambda: self.export_atvise_symbol_file(include_disabled=False))
        menu.add_cascade(label="Export", menu=export_menu)

    def _build_devices_tab(self):
        tab = ttk.Frame(self.tabs, padding=8); self.tabs.add(tab, text="Devices & Requests")
        pane = ttk.Panedwindow(tab, orient="vertical"); pane.pack(fill="both", expand=True)
        upper = ttk.Frame(pane); lower = ttk.Frame(pane); pane.add(upper, weight=3); pane.add(lower, weight=2)
        self.devices_tree = self._tree(upper, [
            ("name", "Device", 180), ("slave", "Slave ID", 80), ("conn", "Connection", 150),
            ("period", "Period", 80), ("timeout", "Timeout", 80), ("enabled", "Enabled", 80),
        ])
        self.devices_tree.pack(fill="both", expand=True); self.devices_tree.bind("<<TreeviewSelect>>", lambda _e: self.refresh_requests())
        db = ttk.Frame(upper); db.pack(fill="x", pady=(6, 4))
        ttk.Button(db, text="Add device", command=self.add_device).pack(side="left", padx=3)
        ttk.Button(db, text="Edit device", command=self.edit_device).pack(side="left", padx=3)
        ttk.Button(db, text="Delete device", command=self.delete_device).pack(side="left", padx=3)
        ttk.Label(lower, text="Requests for selected RTU device").pack(anchor="w")
        self.requests_tree = self._tree(lower, [
            ("name", "Request", 170), ("fc", "FC", 50), ("reg", "Register", 80),
            ("count", "Count / Values", 110), ("dtype", "Data type", 110), ("order", "Byte order", 140), ("enabled", "Enabled", 70),
        ])
        self.requests_tree.pack(fill="both", expand=True)
        rb = ttk.Frame(lower); rb.pack(fill="x", pady=(6, 0))
        ttk.Button(rb, text="Add request", command=self.add_request).pack(side="left", padx=3)
        ttk.Button(rb, text="Edit request", command=self.edit_request).pack(side="left", padx=3)
        ttk.Button(rb, text="Delete request", command=self.delete_request).pack(side="left", padx=3)

    def _build_mappings_tab(self):
        tab = ttk.Frame(self.tabs, padding=8); self.tabs.add(tab, text="TCP Mappings")
        self.mappings_tree = self._tree(tab, [
            ("name", "Name", 160), ("device", "Source device", 130), ("request", "Request", 130),
            ("type", "TCP type", 120), ("register", "Register", 75), ("perm", "Access (auto)", 85),
            ("dtype", "Data type", 85), ("count", "Count", 55), ("enabled", "Enabled", 65),
        ])
        self.mappings_tree.pack(fill="both", expand=True)
        buttons = ttk.Frame(tab); buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(buttons, text="Add", command=self.add_mapping).pack(side="left", padx=3)
        ttk.Button(buttons, text="Edit", command=self.edit_mapping).pack(side="left", padx=3)
        ttk.Button(buttons, text="Delete", command=self.delete_mapping).pack(side="left", padx=3)

    def _build_tcp_server_tab(self):
        self._build_tcp_clients_tab()
        super()._build_tcp_server_tab()

    def _build_tcp_clients_tab(self):
        tab = ttk.Frame(self.tabs, padding=8); self.tabs.add(tab, text="Modbus TCP Clients")
        pane = ttk.Panedwindow(tab, orient="vertical"); pane.pack(fill="both", expand=True)
        upper = ttk.Frame(pane); lower = ttk.Frame(pane); pane.add(upper, weight=3); pane.add(lower, weight=2)

        self.tcp_clients_tree = self._tree(upper, [
            ("name", "Name", 180), ("host", "Host / IP", 180), ("port", "Port", 70),
            ("unit", "Unit ID", 70), ("period", "Period", 70), ("timeout", "Timeout", 70), ("enabled", "Enabled", 70),
        ])
        self.tcp_clients_tree.pack(fill="both", expand=True)
        self.tcp_clients_tree.bind("<<TreeviewSelect>>", lambda _e: self.refresh_tcp_client_requests())
        buttons = ttk.Frame(upper); buttons.pack(fill="x", pady=(6, 4))
        ttk.Button(buttons, text="Add TCP client", command=self.add_tcp_client).pack(side="left", padx=3)
        ttk.Button(buttons, text="Edit TCP client", command=self.edit_tcp_client).pack(side="left", padx=3)
        ttk.Button(buttons, text="Delete TCP client", command=self.delete_tcp_client).pack(side="left", padx=3)

        ttk.Label(lower, text="Requests for selected TCP client").pack(anchor="w")
        self.tcp_client_requests_tree = self._tree(lower, [
            ("name", "Request", 170), ("fc", "FC", 50), ("reg", "Register", 80),
            ("count", "Count / Values", 110), ("dtype", "Data type", 110), ("order", "Byte order", 140), ("enabled", "Enabled", 70),
        ])
        self.tcp_client_requests_tree.pack(fill="both", expand=True)
        rb = ttk.Frame(lower); rb.pack(fill="x", pady=(6, 0))
        ttk.Button(rb, text="Add request", command=self.add_tcp_client_request).pack(side="left", padx=3)
        ttk.Button(rb, text="Edit request", command=self.edit_tcp_client_request).pack(side="left", padx=3)
        ttk.Button(rb, text="Delete request", command=self.delete_tcp_client_request).pack(side="left", padx=3)

    def refresh_all(self):
        super().refresh_all()
        self.refresh_tcp_clients()
        self.refresh_tcp_client_requests()

    def refresh_requests(self):
        self._clear(self.requests_tree)
        idx = self.selected_device_index()
        if idx is None or idx >= len(self.project.devices): return
        for i, r in enumerate(self.project.devices[idx].requests):
            cv = r.values if r.function.is_write else r.count
            dtype = r.raw_data_type or r.data_type
            self.requests_tree.insert("", "end", iid=str(i), values=(r.name, int(r.function), r.register, cv, dtype, r.byte_order, "Yes" if r.enabled else "No"))

    def selected_tcp_client_index(self):
        sel = self.tcp_clients_tree.selection()
        return int(sel[0]) if sel else None

    def refresh_tcp_clients(self):
        selected = self.tcp_clients_tree.selection()
        self._clear(self.tcp_clients_tree)
        for i, d in enumerate(self.project.tcp_clients):
            self.tcp_clients_tree.insert("", "end", iid=str(i), values=(d.name, d.host, d.port, d.unit_id, d.period, d.timeout, "Yes" if d.enabled else "No"))
        if selected and selected[0] in self.tcp_clients_tree.get_children():
            self.tcp_clients_tree.selection_set(selected[0])

    def refresh_tcp_client_requests(self):
        self._clear(self.tcp_client_requests_tree)
        idx = self.selected_tcp_client_index()
        if idx is None or idx >= len(self.project.tcp_clients): return
        for i, r in enumerate(self.project.tcp_clients[idx].requests):
            cv = r.values if r.function.is_write else r.count
            dtype = r.raw_data_type or r.data_type
            self.tcp_client_requests_tree.insert("", "end", iid=str(i), values=(r.name, int(r.function), r.register, cv, dtype, r.byte_order, "Yes" if r.enabled else "No"))

    def _tcp_client_dialog(self, initial=None):
        dlg = FormDialog(self, "Modbus TCP Client", [
            ("name", "Name", "text", None), ("host", "Host / IP", "text", None), ("port", "Port", "text", None),
            ("unit_id", "Unit / Server ID", "text", None), ("period", "Polling period", "text", None),
            ("timeout", "Timeout", "text", None), ("enabled", "Enabled", "bool", None),
        ], initial or {})
        return dlg.values

    def add_tcp_client(self):
        v = self._tcp_client_dialog({"host": "", "port": 502, "unit_id": 1, "period": 10, "timeout": 1, "enabled": False})
        if not v: return
        self.project.tcp_clients.append(TcpClientDevice(name=v["name"], host=v["host"].strip(), port=int(v["port"]), unit_id=int(v["unit_id"]),
                                                        period=int(v["period"]), timeout=int(v["timeout"]), enabled=bool(v["enabled"])))
        self.mark_dirty(); self.refresh_all()

    def edit_tcp_client(self):
        i = self.selected_tcp_client_index()
        if i is None: return
        d = self.project.tcp_clients[i]
        v = self._tcp_client_dialog(vars_for(d))
        if not v: return
        old = d.name
        d.name = v["name"]; d.host = v["host"].strip(); d.port = int(v["port"]); d.unit_id = int(v["unit_id"])
        d.period = int(v["period"]); d.timeout = int(v["timeout"]); d.enabled = bool(v["enabled"])
        if old != d.name:
            for m in self.project.mappings:
                if m.device == old: m.device = d.name
        self.mark_dirty(); self.refresh_all()

    def delete_tcp_client(self):
        i = self.selected_tcp_client_index()
        if i is None: return
        name = self.project.tcp_clients[i].name
        if any(m.device == name for m in self.project.mappings):
            messagebox.showerror("TCP client in use", "Delete TCP mappings that reference this client first.", parent=self); return
        del self.project.tcp_clients[i]
        self.mark_dirty(); self.refresh_all()

    def _request_for_mapping(self, device_name: str, request_name: str):
        source = next((d for d in self.project.devices if d.name == device_name), None)
        if source is None:
            source = next((d for d in self.project.tcp_clients if d.name == device_name), None)
        if source is None: return None
        return next((r for r in source.requests if r.name == request_name), None)

    def refresh_mappings(self):
        self._clear(self.mappings_tree)
        for i, m in enumerate(self.project.mappings):
            request = self._request_for_mapping(m.device, m.request)
            access = permissions_for_function(request.function) if request else m.permissions
            self.mappings_tree.insert("", "end", iid=str(i), values=(m.name, m.device, m.request, m.register_type, m.register, access, m.data_type, m.count, "Yes" if m.enabled else "No"))

    def _request_dialog(self, initial=None):
        initial = dict(initial or {})
        if "function" in initial and not isinstance(initial["function"], str): initial["function"] = _fc_text(initial["function"])
        elif str(initial.get("function", "")).isdigit(): initial["function"] = _fc_text(int(initial["function"]))
        dlg = FormDialog(self, "Request", [
            ("name", "Name", "text", None), ("function", "Function", "choice", FUNCTION_CHOICES),
            ("register", "First register", "text", None), ("count", "Read count", "text", None),
            ("values", "Write value(s)", "text", None), ("data_type", "Data type", "choice", REQUEST_DATA_TYPES),
            ("byte_order", "Byte order", "choice", BYTE_ORDERS), ("enabled", "Enabled", "bool", None),
        ], initial)
        return dlg.values

    @staticmethod
    def _request_from_values(v, *, source_id=None):
        fc = _parse_fc(v["function"])
        return Request(name=v["name"], function=fc, register=int(v["register"]), count=int(v["count"] or 1), data_type=v["data_type"],
                       byte_order=v["byte_order"], enabled=bool(v["enabled"]), values=(v["values"].strip() or None), source_id=source_id)

    def add_request(self):
        i = self.selected_device_index()
        if i is None: return
        v = self._request_dialog({"function": _fc_text(4), "register": 0, "count": 1, "values": "", "data_type": "int16", "byte_order": "high_byte_first", "enabled": True})
        if not v: return
        self.project.devices[i].requests.append(self._request_from_values(v))
        self.mark_dirty(); self.refresh_requests()

    def edit_request(self):
        di = self.selected_device_index(); sel = self.requests_tree.selection()
        if di is None or not sel: return
        ri = int(sel[0]); r = self.project.devices[di].requests[ri]
        initial = vars_for(r) | {"function": _fc_text(r.function), "values": r.values or ""}
        if r.raw_data_type:
            messagebox.showerror("Raw RutOS datatype", "This imported request uses an unrecognized raw RutOS datatype token. It is preserved losslessly but is not editable yet.", parent=self); return
        v = self._request_dialog(initial)
        if not v: return
        old = r.name; replacement = self._request_from_values(v, source_id=r.source_id)
        self.project.devices[di].requests[ri] = replacement
        if old != replacement.name:
            for m in self.project.mappings:
                if m.device == self.project.devices[di].name and m.request == old: m.request = replacement.name
        for m in self.project.mappings:
            if m.device == self.project.devices[di].name and m.request == replacement.name:
                m.permissions = permissions_for_function(replacement.function)
        self.mark_dirty(); self.refresh_all()

    def add_tcp_client_request(self):
        i = self.selected_tcp_client_index()
        if i is None: return
        v = self._request_dialog({"function": _fc_text(4), "register": 0, "count": 1, "values": "", "data_type": "int16", "byte_order": "high_byte_first", "enabled": False})
        if not v: return
        self.project.tcp_clients[i].requests.append(self._request_from_values(v))
        self.mark_dirty(); self.refresh_tcp_client_requests()

    def edit_tcp_client_request(self):
        di = self.selected_tcp_client_index(); sel = self.tcp_client_requests_tree.selection()
        if di is None or not sel: return
        ri = int(sel[0]); r = self.project.tcp_clients[di].requests[ri]
        if r.raw_data_type:
            messagebox.showerror("Raw RutOS datatype", "This imported request uses an unrecognized raw RutOS datatype token. It is preserved losslessly but is not editable yet.", parent=self); return
        initial = vars_for(r) | {"function": _fc_text(r.function), "values": r.values or ""}
        v = self._request_dialog(initial)
        if not v: return
        old = r.name; replacement = self._request_from_values(v, source_id=r.source_id)
        self.project.tcp_clients[di].requests[ri] = replacement
        source_name = self.project.tcp_clients[di].name
        if old != replacement.name:
            for m in self.project.mappings:
                if m.device == source_name and m.request == old: m.request = replacement.name
        for m in self.project.mappings:
            if m.device == source_name and m.request == replacement.name:
                m.permissions = permissions_for_function(replacement.function)
        self.mark_dirty(); self.refresh_all()

    def delete_tcp_client_request(self):
        di = self.selected_tcp_client_index(); sel = self.tcp_client_requests_tree.selection()
        if di is None or not sel: return
        ri = int(sel[0]); source = self.project.tcp_clients[di]; name = source.requests[ri].name
        if any(m.device == source.name and m.request == name for m in self.project.mappings):
            messagebox.showerror("Request in use", "Delete TCP mappings that reference this request first.", parent=self); return
        del source.requests[ri]
        self.mark_dirty(); self.refresh_tcp_client_requests()

    def _mapping_dialog(self, initial=None):
        source_names = [d.name for d in self.project.devices] + [d.name for d in self.project.tcp_clients]
        devices = tuple(source_names) or ("",)
        dlg = FormDialog(self, "TCP Mapping", [
            ("name", "Name", "text", None), ("device", "Source device", "choice", devices),
            ("request", "Request name", "text", None), ("register_type", "TCP register type", "choice", REGISTER_TYPES),
            ("register", "TCP register", "text", None),
            ("data_type", "Register data type", "choice", TCP_DATA_TYPES), ("count", "Value count", "text", None),
            ("enabled", "Enabled", "bool", None),
        ], initial)
        return dlg.values

    def _mapping_access(self, device_name: str, request_name: str) -> str:
        request = self._request_for_mapping(device_name, request_name)
        if request is None:
            raise ValueError(f"Unknown source request {device_name}/{request_name}")
        return permissions_for_function(request.function)

    def add_mapping(self):
        sources = list(self.project.devices) + list(self.project.tcp_clients)
        if not sources: messagebox.showerror("No devices", "Create an RTU or Modbus TCP Client device first."); return
        v = self._mapping_dialog({"device": sources[0].name, "register_type": "input_register", "register": 1025, "data_type": "int16", "count": 1, "enabled": True})
        if not v: return
        access = self._mapping_access(v["device"], v["request"])
        self.project.mappings.append(ServerMapping(name=v["name"], device=v["device"], request=v["request"], register=int(v["register"]), register_type=v["register_type"], enabled=bool(v["enabled"]), permissions=access, data_type=v["data_type"], count=int(v["count"])))
        self.mark_dirty(); self.refresh_mappings()

    def edit_mapping(self):
        sel = self.mappings_tree.selection()
        if not sel: return
        i = int(sel[0]); m = self.project.mappings[i]; v = self._mapping_dialog(vars_for(m))
        if not v: return
        access = self._mapping_access(v["device"], v["request"])
        source_id = m.source_id
        self.project.mappings[i] = ServerMapping(name=v["name"], device=v["device"], request=v["request"], register=int(v["register"]), register_type=v["register_type"], enabled=bool(v["enabled"]), permissions=access, data_type=v["data_type"], count=int(v["count"]), source_id=source_id)
        self.mark_dirty(); self.refresh_mappings()

    def open_bulk_generator(self):
        if not self.project.connections:
            messagebox.showerror("Bulk generator", "Create or import at least one serial connection first.", parent=self); return
        BulkGeneratorWindow(self, self.project, self._bulk_applied)

    def _bulk_applied(self):
        self.mark_dirty(); self.refresh_all(); self.status.set("Bulk batch added to project; validate and save before deployment")

    def export_atvise_symbol_file(self, *, include_disabled: bool = True):
        try:
            text = export_atvise_symbols(self.project, include_disabled=include_disabled)
        except Exception as exc:
            messagebox.showerror("atvise symbol export", str(exc), parent=self); return
        selected = [m for m in self.project.mappings if include_disabled or m.enabled]
        if not selected:
            messagebox.showerror("atvise symbol export", "There are no TCP mappings to export.", parent=self); return
        default_name = self.path.stem if self.path else "Teltonika_Modbus"
        filename = filedialog.asksaveasfilename(parent=self, title="Export atvise Connect Symbol file", defaultextension=".Symbol", initialfile=f"{default_name}.Symbol", filetypes=[("atvise Connect Symbol", "*.Symbol"), ("All files", "*.*")])
        if not filename: return
        try:
            with open(filename, "w", encoding="utf-8", newline="\n") as handle: handle.write(text)
            self.status.set(f"Exported {len(selected)} atvise symbol(s) to {filename}")
            messagebox.showinfo("atvise symbol export", f"Exported {len(selected)} symbol(s).\n\n{filename}", parent=self)
        except Exception as exc:
            messagebox.showerror("atvise symbol export", str(exc), parent=self)


def main():
    ExtendedProjectEditor().mainloop()

if __name__ == "__main__":
    main()
