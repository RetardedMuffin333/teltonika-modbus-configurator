"""v0.4 GUI entry point with Carel cDesign import planning."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .carel_convert import apply_carel_import_plan, build_carel_import_plan
from .carel_import import load_carel_xls
from .gui_scada import ScadaProjectEditor


class CarelProjectEditor(ScadaProjectEditor):
    def _build_menu(self):
        super()._build_menu()
        menu = self.nametowidget(self.cget("menu"))
        import_menu = tk.Menu(menu, tearoff=False)
        import_menu.add_command(label="Carel cDesign XLS import...", command=self.preview_carel_xls)
        menu.add_cascade(label="Carel", menu=import_menu)

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
        self.title("Carel cDesign XLS import")
        self.geometry("1450x760")
        self.transient(parent)

        summary = (
            f"File: {preview.path}\n"
            f"Sheets: {', '.join(preview.sheets) or '<none>'}\n"
            f"Detected header row: {preview.header_row or '<not detected>'}   "
            f"Candidate rows: {len(preview.rows)}"
        )
        ttk.Label(self, text=summary, justify="left").pack(fill="x", padx=10, pady=(10, 5))

        options = ttk.LabelFrame(self, text="Import options")
        options.pack(fill="x", padx=10, pady=(0, 7))
        ttk.Label(options, text="Target Modbus TCP client:").grid(row=0, column=0, padx=6, pady=6, sticky="w")
        self.device_var = tk.StringVar()
        devices = [d.name for d in parent.project.tcp_clients]
        self.device_box = ttk.Combobox(options, textvariable=self.device_var, values=devices, state="readonly", width=28)
        self.device_box.grid(row=0, column=1, padx=6, pady=6, sticky="w")
        if devices:
            self.device_var.set(devices[0])

        self.add_one_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            options,
            text="Carel Index + 1 for RutOS request address",
            variable=self.add_one_var,
        ).grid(row=0, column=2, padx=14, pady=6, sticky="w")

        ttk.Label(options, text="TCP Server mapping start:").grid(row=0, column=3, padx=(14, 4), pady=6, sticky="w")
        self.start_var = tk.StringVar(value="1025")
        ttk.Entry(options, textvariable=self.start_var, width=8).grid(row=0, column=4, padx=4, pady=6, sticky="w")
        ttk.Button(options, text="Build import plan", command=self.build_plan).grid(row=0, column=5, padx=10, pady=6)

        self.tree = ttk.Treeview(
            self,
            columns=("name", "carel", "area", "dtype", "direction", "fc", "rutos", "server", "status"),
            show="headings",
        )
        for key, title, width in (
            ("name", "Name", 330), ("carel", "Carel index", 80), ("area", "Modbus type", 120),
            ("dtype", "Data type", 85), ("direction", "Direction", 85), ("fc", "FC", 42),
            ("rutos", "RutOS addr", 75), ("server", "TCP Server", 105), ("status", "Status", 260),
        ):
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        for row in preview.rows:
            self.tree.insert("", "end", values=(row.name, row.register, row.modbus_type, row.data_type, row.access, "", "", "", "Parsed"))

        footer = ttk.Frame(self)
        footer.pack(fill="x", padx=10, pady=(0, 10))
        self.info_var = tk.StringVar(
            value="Parse preview only. Build an import plan before anything is added to the project."
        )
        ttk.Label(footer, textvariable=self.info_var).pack(side="left")
        ttk.Button(footer, text="Close", command=self.destroy).pack(side="right")
        self.import_button = ttk.Button(footer, text="Import ready rows", command=self.apply_plan, state="disabled")
        self.import_button.pack(side="right", padx=(0, 8))

    def build_plan(self):
        if not self.device_var.get():
            messagebox.showerror("Carel import", "Create or select a Modbus TCP client first.", parent=self)
            return
        try:
            start = int(self.start_var.get())
            self.plan = build_carel_import_plan(
                self.parent.project,
                self.preview.rows,
                tcp_device_name=self.device_var.get(),
                add_one_to_index=self.add_one_var.get(),
                mapping_start=start,
            )
        except Exception as exc:
            messagebox.showerror("Carel import", str(exc), parent=self)
            return

        for item_id in self.tree.get_children():
            self.tree.delete(item_id)
        ready = 0
        skipped = 0
        for item in self.plan:
            request = item.request
            mapping = item.mapping
            if request and mapping:
                ready += 1
                server = f"{mapping.register_type}:{mapping.register}"
                fc = int(request.function)
                rutos = request.register
            else:
                skipped += 1
                server = ""
                fc = ""
                rutos = ""
            row = item.source
            self.tree.insert(
                "",
                "end",
                values=(row.name, row.register, row.modbus_type, row.data_type, row.access, fc, rutos, server, item.status),
            )
        self.info_var.set(f"Plan: {ready} ready, {skipped} skipped. ReadWrite rows create the read path only in this stage.")
        self.import_button.configure(state="normal" if ready else "disabled")

    def apply_plan(self):
        if not self.plan:
            return
        ready = sum(1 for item in self.plan if item.request is not None and item.mapping is not None)
        if not messagebox.askyesno(
            "Carel import",
            f"Import {ready} ready Carel variables into {self.device_var.get()}?\n\n"
            "This adds requests and TCP Server mappings to the current project. It does not deploy to RutOS.",
            parent=self,
        ):
            return
        try:
            count = apply_carel_import_plan(
                self.parent.project,
                self.plan,
                tcp_device_name=self.device_var.get(),
            )
        except Exception as exc:
            messagebox.showerror("Carel import", str(exc), parent=self)
            return
        self.parent.mark_dirty()
        self.parent.refresh_all()
        self.import_button.configure(state="disabled")
        self.info_var.set(f"Imported {count} Carel variables into the project. Review mappings and Validate before deployment.")
        messagebox.showinfo("Carel import", f"Imported {count} Carel variables.", parent=self)


def main() -> None:
    CarelProjectEditor().mainloop()


if __name__ == "__main__":
    main()
