"""v0.4 usability layer for large Modbus projects.

Keeps Carel import conservative while making large request/mapping sets easier to
work with: double-click edits, multi-delete, and deliberate multi-select SCADA
write-target creation.
"""

from __future__ import annotations

from tkinter import messagebox

from .gui_carel import CarelProjectEditor
from .scada_write import create_scada_write_target


def selected_numeric_indices(selection) -> list[int]:
    """Return selected numeric Treeview iids in descending order."""
    result = []
    for iid in selection:
        try:
            result.append(int(iid))
        except (TypeError, ValueError):
            continue
    return sorted(set(result), reverse=True)


def selected_mapping_indices(selection) -> list[int]:
    """Return selected grouped mapping indices in descending order."""
    result = []
    for iid in selection:
        if not str(iid).startswith("mapping::"):
            continue
        try:
            result.append(int(str(iid).split("::", 1)[1]))
        except ValueError:
            continue
    return sorted(set(result), reverse=True)


class UsableCarelProjectEditor(CarelProjectEditor):
    """Carel editor optimized for projects with hundreds of requests/mappings."""

    def _build_devices_tab(self):
        super()._build_devices_tab()
        self.requests_tree.configure(selectmode="extended")
        self.requests_tree.bind("<Double-1>", self._double_click_rtu_request)

    def _build_tcp_clients_tab(self):
        super()._build_tcp_clients_tab()
        self.tcp_client_requests_tree.configure(selectmode="extended")
        self.tcp_client_requests_tree.bind("<Double-1>", self._double_click_tcp_request)

    def _build_mappings_tab(self):
        super()._build_mappings_tab()
        self.mappings_tree.configure(selectmode="extended")
        self.mappings_tree.bind("<Double-1>", self._double_click_mapping)

    @staticmethod
    def _clicked_row(tree, event):
        return tree.identify_row(event.y)

    def _double_click_rtu_request(self, event):
        iid = self._clicked_row(self.requests_tree, event)
        if iid:
            self.requests_tree.selection_set(iid)
            self.edit_request()
        return "break"

    def _double_click_tcp_request(self, event):
        iid = self._clicked_row(self.tcp_client_requests_tree, event)
        if iid:
            self.tcp_client_requests_tree.selection_set(iid)
            self.edit_tcp_client_request()
        return "break"

    def _double_click_mapping(self, event):
        iid = self._clicked_row(self.mappings_tree, event)
        if not iid:
            return "break"
        if iid.startswith("mapping::"):
            self.mappings_tree.selection_set(iid)
            self.edit_mapping()
        else:
            # Device group rows remain expand/collapse controls rather than editable objects.
            self.mappings_tree.item(iid, open=not self.mappings_tree.item(iid, "open"))
        return "break"

    def delete_request(self):
        device_index = self.selected_device_index()
        indices = selected_numeric_indices(self.requests_tree.selection())
        if device_index is None or not indices:
            return
        source = self.project.devices[device_index]
        names = [source.requests[i].name for i in indices if 0 <= i < len(source.requests)]
        blocked = [name for name in names if any(m.device == source.name and m.request == name for m in self.project.mappings)]
        if blocked:
            messagebox.showerror(
                "Requests in use",
                "Delete the TCP Server mappings for these requests first:\n\n" + "\n".join(blocked),
                parent=self,
            )
            return
        if len(indices) > 1 and not messagebox.askyesno("Delete requests", f"Delete {len(indices)} selected RTU requests?", parent=self):
            return
        for index in indices:
            if 0 <= index < len(source.requests):
                del source.requests[index]
        self.mark_dirty()
        self.refresh_requests()

    def delete_tcp_client_request(self):
        device_index = self.selected_tcp_client_index()
        indices = selected_numeric_indices(self.tcp_client_requests_tree.selection())
        if device_index is None or not indices:
            return
        source = self.project.tcp_clients[device_index]
        names = [source.requests[i].name for i in indices if 0 <= i < len(source.requests)]
        blocked = [name for name in names if any(m.device == source.name and m.request == name for m in self.project.mappings)]
        if blocked:
            messagebox.showerror(
                "Requests in use",
                "Delete the TCP Server mappings for these requests first:\n\n" + "\n".join(blocked),
                parent=self,
            )
            return
        if len(indices) > 1 and not messagebox.askyesno("Delete requests", f"Delete {len(indices)} selected TCP requests?", parent=self):
            return
        for index in indices:
            if 0 <= index < len(source.requests):
                del source.requests[index]
        self.mark_dirty()
        self.refresh_tcp_client_requests()

    def delete_mapping(self):
        indices = selected_mapping_indices(self.mappings_tree.selection())
        if not indices:
            messagebox.showinfo("TCP mapping", "Expand a source device and select one or more mappings to delete.", parent=self)
            return
        if len(indices) > 1 and not messagebox.askyesno("Delete mappings", f"Delete {len(indices)} selected TCP Server mappings?", parent=self):
            return
        for index in indices:
            if 0 <= index < len(self.project.mappings):
                del self.project.mappings[index]
        self.mark_dirty()
        self.refresh_mappings()

    def _create_selected_scada_targets(self, *, device_name: str, request_names: list[str]):
        if not request_names:
            return
        created = []
        failed = []
        for request_name in request_names:
            try:
                target = create_scada_write_target(
                    self.project,
                    device_name=device_name,
                    read_request_name=request_name,
                    # New deliberate v0.4 command targets stay far from large read maps.
                    write_block_start=20000,
                )
                created.append(target.request.name)
            except Exception as exc:
                failed.append(f"{request_name}: {exc}")

        if created:
            self.mark_dirty()
            self.refresh_all()
            self.status.set(f"Created {len(created)} SCADA write target(s) in the 20000+ write block")

        text = ""
        if created:
            text += f"Created {len(created)} write target(s):\n" + "\n".join(created)
        if failed:
            if text:
                text += "\n\n"
            text += f"Skipped/failed {len(failed)}:\n" + "\n".join(failed)
        messagebox.showinfo("SCADA write targets", text or "No write targets created.", parent=self)

    def create_rtu_scada_write_target(self):
        device_index = self.selected_device_index()
        indices = sorted(selected_numeric_indices(self.requests_tree.selection()))
        if device_index is None or not indices:
            messagebox.showerror("SCADA write target", "Select one or more RTU FC03/FC01 feedback requests first.", parent=self)
            return
        device = self.project.devices[device_index]
        names = [device.requests[i].name for i in indices if 0 <= i < len(device.requests)]
        self._create_selected_scada_targets(device_name=device.name, request_names=names)

    def create_tcp_scada_write_target(self):
        device_index = self.selected_tcp_client_index()
        indices = sorted(selected_numeric_indices(self.tcp_client_requests_tree.selection()))
        if device_index is None or not indices:
            messagebox.showerror("SCADA write target", "Select one or more TCP FC03/FC01 feedback requests first.", parent=self)
            return
        device = self.project.tcp_clients[device_index]
        names = [device.requests[i].name for i in indices if 0 <= i < len(device.requests)]
        self._create_selected_scada_targets(device_name=device.name, request_names=names)


def main() -> None:
    UsableCarelProjectEditor().mainloop()


if __name__ == "__main__":
    main()
