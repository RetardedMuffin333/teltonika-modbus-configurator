"""v0.4 GUI entry point with Carel cDesign import planning."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .carel_convert import apply_carel_import_plan, build_carel_import_plan
from .carel_import import load_carel_xls
from .gui import vars_for
from .gui_scada import ScadaProjectEditor
from .models import ServerMapping


class CarelProjectEditor(ScadaProjectEditor):
    def _build_menu(self):
        super()._build_menu()
        menu = self.nametowidget(self.cget("menu"))
        import_menu = tk.Menu(menu, tearoff=False)
        import_menu.add_command(label="Carel cDesign XLS import...", command=self.preview_carel_xls)
        menu.add_cascade(label="Carel", menu=import_menu)

    def _build_mappings_tab(self):
        """Show TCP Server mappings grouped by source device."""
        tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(tab, text="TCP Server Mappings")
        self.mappings_tree = ttk.Treeview(
            tab,
            columns=("request", "type", "register", "perm", "dtype", "count", "enabled"),
            show="tree headings",
            selectmode="browse",
        )
        self.mappings_tree.heading("#0", text="Source device / Mapping")
        self.mappings_tree.column("#0", width=280, anchor="w")
        for key, title, width in (
            ("request", "Request", 190), ("type", "TCP type", 125), ("register", "Register", 75),
            ("perm", "Access (auto)", 90), ("dtype", "Data type", 90), ("count", "Count", 55),
            ("enabled", "Enabled", 65),
        ):
            self.mappings_tree.heading(key, text=title)
            self.mappings_tree.column(key, width=width, anchor="w")
        self.mappings_tree.pack(fill="both", expand=True)
        buttons = ttk.Frame(tab)
        buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(buttons, text="Add", command=self.add_mapping).pack(side="left", padx=3)
        ttk.Button(buttons, text="Edit", command=self.edit_mapping).pack(side="left", padx=3)
        ttk.Button(buttons, text="Delete", command=self.delete_mapping).pack(side="left", padx=3)
        ttk.Button(buttons, text="Expand all", command=lambda: self._set_mapping_groups_open(True)).pack(side="right", padx=3)
        ttk.Button(buttons, text="Collapse all", command=lambda: self._set_mapping_groups_open(False)).pack(side="right", padx=3)

    def _mapping_index_from_selection(self):
        selected = self.mappings_tree.selection()
        if not selected:
            return None
        iid = selected[0]
        if not iid.startswith("mapping::"):
            return None
        try:
            return int(iid.split("::", 1)[1])
        except ValueError:
            return None

    def _set_mapping_groups_open(self, opened: bool):
        for iid in self.mappings_tree.get_children(""):
            self.mappings_tree.item(iid, open=opened)

    def refresh_mappings(self):
        open_devices = set()
        for iid in self.mappings_tree.get_children(""):
            if self.mappings_tree.item(iid, "open"):
                values = self.mappings_tree.item(iid, "values")
                if values:
                    open_devices.add(values[0])
        for iid in self.mappings_tree.get_children(""):
            self.mappings_tree.delete(iid)

        grouped: dict[str, list[tuple[int, object]]] = {}
        for index, mapping in enumerate(self.project.mappings):
            grouped.setdefault(mapping.device, []).append((index, mapping))

        for device_number, (device_name, mappings) in enumerate(grouped.items()):
            parent_iid = f"device::{device_number}"
            self.mappings_tree.insert(
                "", "end", iid=parent_iid,
                text=f"{device_name}  ({len(mappings)} mappings)",
                values=(device_name, "", "", "", "", "", ""),
                open=device_name in open_devices,
            )
            for index, mapping in mappings:
                request = self._request_for_mapping(mapping.device, mapping.request)
                access = request.function and ("r" if request.function.is_read else "w") if request else mapping.permissions
                self.mappings_tree.insert(
                    parent_iid, "end", iid=f"mapping::{index}", text=mapping.name,
                    values=(
                        mapping.request, mapping.register_type, mapping.register, access,
                        mapping.data_type, mapping.count, "Yes" if mapping.enabled else "No",
                    ),
                )

    def edit_mapping(self):
        index = self._mapping_index_from_selection()
        if index is None:
            messagebox.showinfo("TCP mapping", "Expand a source device and select a mapping to edit.", parent=self)
            return
        mapping = self.project.mappings[index]
        values = self._mapping_dialog(vars_for(mapping))
        if not values:
            return
        access = self._mapping_access(values["device"], values["request"])
        self.project.mappings[index] = ServerMapping(
            name=values["name"], device=values["device"], request=values["request"],
            register=int(values["register"]), register_type=values["register_type"],
            enabled=bool(values["enabled"]), permissions=access, data_type=values["data_type"],
            count=int(values["count"]), source_id=mapping.source_id,
        )
        self.mark_dirty()
        self.refresh_mappings()

    def delete_mapping(self):
        index = self._mapping_index_from_selection()
        if index is None:
            messagebox.showinfo("TCP mapping", "Expand a source device and select a mapping to delete.", parent=self)
            return
        del self.project.mappings[index]
        self.mark_dirty()
        self.refresh_mappings()

    def preview_carel_xls(self):
        filename = filedialog.askopenfilename(
            parent=self,
            title="Open Carel cDesign Modbus export",
            filetypes=[("Carel / Excel 97-2003", "*.xls"), ("All files", "*.*")],
        )
        if not filename:
            return
        try:
            preview = load_carel_xls(filename)
        except Exception as exc:
            messagebox.showerror("Carel import", str(exc), parent=self)
            return
        CarelPreviewWindow(self, preview)


class CarelPreviewWindow(tk.Toplevel):
    def __init__(self, parent: CarelProjectEditor, preview):
        super().__init__(parent)
        self.parent = parent
        self.preview = preview
        self.plan = []
        self.plan_by_iid = {}
        self.title("Carel cDesign XLS import")
        self.geometry("1450x820")
        self.transient(parent)

        summary = (
            f"File: {preview.path}\n"
            f"Sheets: {', '.join(preview.sheets) or '<none>'}\n"
            f"Detected header row: {preview.header_row or '<not detected>'}   Candidate rows: {len(preview.rows)}"
        )
        ttk.Label(self, text=summary, justify="left").pack(fill="x", padx=10, pady=(10, 5))

        options = ttk.LabelFrame(self, text="Import options")
        options.pack(fill="x", padx=10, pady=(0, 5))
        ttk.Label(options, text="Target Modbus TCP client:").grid(row=0, column=0, padx=6, pady=6, sticky="w")
        self.device_var = tk.StringVar()
        devices = [d.name for d in parent.project.tcp_clients]
        self.device_box = ttk.Combobox(options, textvariable=self.device_var, values=devices, state="readonly", width=26)
        self.device_box.grid(row=0, column=1, padx=6, pady=6, sticky="w")
        if devices:
            self.device_var.set(devices[0])

        self.add_one_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options, text="Carel Index + 1 for RutOS request address", variable=self.add_one_var).grid(row=0, column=2, padx=12, pady=6, sticky="w")
        ttk.Label(options, text="TCP Server mapping start:").grid(row=0, column=3, padx=(12, 4), pady=6, sticky="w")
        self.start_var = tk.StringVar(value="1025")
        ttk.Entry(options, textvariable=self.start_var, width=8).grid(row=0, column=4, padx=4, pady=6, sticky="w")
        ttk.Button(options, text="Build import plan", command=self.build_plan).grid(row=0, column=5, padx=10, pady=6)

        self.write_companions_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            options,
            text="Create SCADA write companions for selected ReadWrite Coil/HoldingRegister values",
            variable=self.write_companions_var,
        ).grid(row=1, column=0, columnspan=6, padx=6, pady=(0, 6), sticky="w")
        ttk.Label(options, text="Automatic write mappings use a separate 20000+ block to stay away from read polling.").grid(row=2, column=0, columnspan=6, padx=24, pady=(0, 6), sticky="w")

        filters = ttk.LabelFrame(self, text="Filters")
        filters.pack(fill="x", padx=10, pady=(0, 7))
        ttk.Label(filters, text="Modbus type:").grid(row=0, column=0, padx=(6, 4), pady=5, sticky="w")
        self.area_var = tk.StringVar(value="All")
        areas = ["All"] + sorted({row.modbus_type for row in preview.rows if row.modbus_type})
        ttk.Combobox(filters, textvariable=self.area_var, values=areas, state="readonly", width=20).grid(row=0, column=1, padx=4, pady=5, sticky="w")
        ttk.Label(filters, text="Direction:").grid(row=0, column=2, padx=(14, 4), pady=5, sticky="w")
        self.direction_var = tk.StringVar(value="All")
        directions = ["All"] + sorted({row.access for row in preview.rows if row.access})
        ttk.Combobox(filters, textvariable=self.direction_var, values=directions, state="readonly", width=16).grid(row=0, column=3, padx=4, pady=5, sticky="w")
        ttk.Button(filters, text="Apply filter", command=self.apply_filter).grid(row=0, column=4, padx=(12, 4), pady=5)
        ttk.Button(filters, text="Select all visible", command=self.select_all_visible).grid(row=0, column=5, padx=4, pady=5)
        ttk.Button(filters, text="Clear selection", command=self.clear_selection).grid(row=0, column=6, padx=4, pady=5)

        self.tree = ttk.Treeview(
            self,
            columns=("name", "carel", "area", "dtype", "direction", "fc", "rutos", "server", "status"),
            show="headings", selectmode="extended",
        )
        for key, title, width in (
            ("name", "Name", 330), ("carel", "Carel index", 80), ("area", "Modbus type", 120),
            ("dtype", "Data type", 85), ("direction", "Direction", 85), ("fc", "FC", 42),
            ("rutos", "RutOS addr", 75), ("server", "TCP Server", 105), ("status", "Status", 260),
        ):
            self.tree.heading(key, text=title); self.tree.column(key, width=width, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        self._populate_parsed_rows(preview.rows)

        footer = ttk.Frame(self); footer.pack(fill="x", padx=10, pady=(0, 10))
        self.info_var = tk.StringVar(value="Parse preview only. Build an import plan before anything is added to the project.")
        ttk.Label(footer, textvariable=self.info_var).pack(side="left")
        ttk.Button(footer, text="Close", command=self.destroy).pack(side="right")
        self.import_button = ttk.Button(footer, text="Import selected ready rows", command=self.apply_plan, state="disabled")
        self.import_button.pack(side="right", padx=(0, 8))

    def _row_visible(self, row) -> bool:
        area = self.area_var.get(); direction = self.direction_var.get()
        return (area == "All" or row.modbus_type == area) and (direction == "All" or row.access == direction)

    def _clear_tree(self):
        for item_id in self.tree.get_children(): self.tree.delete(item_id)

    def _populate_parsed_rows(self, rows):
        self._clear_tree()
        for row in rows:
            if self._row_visible(row):
                self.tree.insert("", "end", values=(row.name, row.register, row.modbus_type, row.data_type, row.access, "", "", "", "Parsed"))

    def _populate_plan_rows(self):
        self._clear_tree(); self.plan_by_iid = {}; ready = 0; skipped = 0
        for index, item in enumerate(self.plan):
            row = item.source
            if not self._row_visible(row): continue
            request = item.request; mapping = item.mapping
            if request and mapping:
                ready += 1; server = f"{mapping.register_type}:{mapping.register}"; fc = int(request.function); rutos = request.register
            else:
                skipped += 1; server = ""; fc = ""; rutos = ""
            iid = self.tree.insert("", "end", values=(row.name, row.register, row.modbus_type, row.data_type, row.access, fc, rutos, server, item.status))
            self.plan_by_iid[iid] = index
        self.info_var.set(f"Visible plan: {ready} ready, {skipped} skipped. Select rows to import; selected rows are compacted again during import.")
        self.import_button.configure(state="normal" if ready else "disabled")

    def apply_filter(self):
        self._populate_plan_rows() if self.plan else self._populate_parsed_rows(self.preview.rows)

    def select_all_visible(self): self.tree.selection_set(self.tree.get_children())
    def clear_selection(self): self.tree.selection_remove(self.tree.selection())

    def build_plan(self):
        if not self.device_var.get():
            messagebox.showerror("Carel import", "Create or select a Modbus TCP client first.", parent=self); return
        try:
            self.plan = build_carel_import_plan(
                self.parent.project, self.preview.rows, tcp_device_name=self.device_var.get(),
                add_one_to_index=self.add_one_var.get(), mapping_start=int(self.start_var.get()),
            )
        except Exception as exc:
            messagebox.showerror("Carel import", str(exc), parent=self); return
        self._populate_plan_rows()

    def apply_plan(self):
        if not self.plan: return
        selected_items = []
        for iid in self.tree.selection():
            plan_index = self.plan_by_iid.get(iid)
            if plan_index is not None:
                item = self.plan[plan_index]
                if item.request is not None and item.mapping is not None: selected_items.append(item)
        if not selected_items:
            messagebox.showwarning("Carel import", "Select at least one ready row to import.", parent=self); return
        extra = "\nSCADA write companions will also be created for selected ReadWrite Coil/HoldingRegister rows." if self.write_companions_var.get() else ""
        if not messagebox.askyesno(
            "Carel import",
            f"Import {len(selected_items)} selected Carel variables into {self.device_var.get()}?\n\n"
            "Selected rows will be packed into compact TCP Server blocks per Modbus type."
            f"{extra}\nThis does not deploy to RutOS.", parent=self,
        ):
            return
        try:
            read_count, write_count = apply_carel_import_plan(
                self.parent.project, selected_items, tcp_device_name=self.device_var.get(),
                mapping_start=int(self.start_var.get()), create_write_companions=self.write_companions_var.get(),
            )
        except Exception as exc:
            messagebox.showerror("Carel import", str(exc), parent=self); return
        self.parent.mark_dirty(); self.parent.refresh_all()
        self.info_var.set(f"Imported {read_count} Carel variables and {write_count} SCADA write companions. Review mappings and Validate before deployment.")
        messagebox.showinfo("Carel import", f"Imported {read_count} Carel variables.\nCreated {write_count} write companions.", parent=self)


def main() -> None:
    CarelProjectEditor().mainloop()


if __name__ == "__main__":
    main()
