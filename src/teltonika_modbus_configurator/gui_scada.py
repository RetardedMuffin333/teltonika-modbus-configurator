"""Workflow GUI with helpers for hardware-verified SCADA write targets."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from . import gui_bulk
from .gui_flow import FlowProjectEditor
from .scada_write import (
    allocate_scada_template_mapping_layout,
    create_scada_write_target,
)


class ScadaProjectEditor(FlowProjectEditor):
    def _build_menu(self):
        super()._build_menu()
        menu = self.nametowidget(self.cget("menu"))
        scada_menu = tk.Menu(menu, tearoff=False)
        scada_menu.add_command(
            label="Create write target from selected RTU request",
            command=self.create_rtu_scada_write_target,
        )
        scada_menu.add_command(
            label="Create write target from selected TCP request",
            command=self.create_tcp_scada_write_target,
        )
        menu.add_cascade(label="SCADA", menu=scada_menu)

    def open_bulk_generator(self):
        # BulkGeneratorWindow resolves this helper from gui_bulk at runtime.
        # Use the SCADA-aware allocator so cloned write-only HR mappings remain
        # in their separate HR1200+ block instead of spanning the read/write gap.
        gui_bulk.allocate_template_mapping_layout = allocate_scada_template_mapping_layout
        super().open_bulk_generator()

    def _create_target(self, *, device_name: str, request_name: str):
        try:
            target = create_scada_write_target(
                self.project,
                device_name=device_name,
                read_request_name=request_name,
            )
        except Exception as exc:
            messagebox.showerror("SCADA write target", str(exc), parent=self)
            return

        self.mark_dirty()
        self.refresh_all()
        self.status.set(
            f"Created {target.request.name}: FC06 disabled, TCP HR{target.mapping.register} write-only"
        )
        messagebox.showinfo(
            "SCADA write target",
            "Created paired SCADA command path:\n\n"
            f"Feedback: {target.feedback_mapping.name} @ HR{target.feedback_mapping.register} (read-only)\n"
            f"Command:  {target.mapping.name} @ HR{target.mapping.register} (write-only)\n\n"
            "The FC06 request is disabled so RutOS will not periodically write its placeholder value.",
            parent=self,
        )

    def create_rtu_scada_write_target(self):
        device_index = self.selected_device_index()
        selected = self.requests_tree.selection()
        if device_index is None or not selected:
            messagebox.showerror(
                "SCADA write target",
                "Select an RTU device and its FC03 feedback request first.",
                parent=self,
            )
            return
        device = self.project.devices[device_index]
        request = device.requests[int(selected[0])]
        self._create_target(device_name=device.name, request_name=request.name)

    def create_tcp_scada_write_target(self):
        device_index = self.selected_tcp_client_index()
        selected = self.tcp_client_requests_tree.selection()
        if device_index is None or not selected:
            messagebox.showerror(
                "SCADA write target",
                "Select a Modbus TCP client and its FC03 feedback request first.",
                parent=self,
            )
            return
        device = self.project.tcp_clients[device_index]
        request = device.requests[int(selected[0])]
        self._create_target(device_name=device.name, request_name=request.name)


def main() -> None:
    ScadaProjectEditor().mainloop()


if __name__ == "__main__":
    main()
