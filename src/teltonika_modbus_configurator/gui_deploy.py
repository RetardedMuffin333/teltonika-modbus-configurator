"""Guarded live deployment actions for the desktop editor."""

from __future__ import annotations

from pathlib import Path
from queue import Empty, Queue
from threading import Thread
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from .deploy import (
    SshSession,
    apply_generated,
    new_snapshot_name,
    read_remote_config,
    render_diff,
    rollback_snapshot,
    save_local_backup,
)
from .gui import ProjectEditor, TextWindow
from .uci_generator import generate_uci
from .validator import validate_project


class DiffConfirmDialog(tk.Toplevel):
    """Modal diff viewer that requires typing APPLY before a write."""

    def __init__(self, parent, diff: str):
        super().__init__(parent)
        self.result = False
        self.title("Review live TRB changes")
        self.geometry("1050x760")
        self.transient(parent)
        self.grab_set()

        ttk.Label(
            self,
            text="Review the complete diff below. Nothing has been written yet.",
        ).pack(anchor="w", padx=10, pady=(10, 4))

        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, padx=10)
        area = tk.Text(frame, wrap="none", font=("Consolas", 9))
        y = ttk.Scrollbar(frame, orient="vertical", command=area.yview)
        x = ttk.Scrollbar(frame, orient="horizontal", command=area.xview)
        area.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        area.grid(row=0, column=0, sticky="nsew")
        y.grid(row=0, column=1, sticky="ns")
        x.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        area.insert("1.0", diff)
        area.configure(state="disabled")

        confirm = ttk.Frame(self)
        confirm.pack(fill="x", padx=10, pady=10)
        ttk.Label(confirm, text="Type APPLY to enable the write:").pack(side="left")
        self.confirm_var = tk.StringVar()
        entry = ttk.Entry(confirm, textvariable=self.confirm_var, width=14)
        entry.pack(side="left", padx=8)
        self.apply_button = ttk.Button(confirm, text="Apply to TRB", command=self._apply, state="disabled")
        self.apply_button.pack(side="right", padx=4)
        ttk.Button(confirm, text="Cancel", command=self.destroy).pack(side="right", padx=4)
        self.confirm_var.trace_add("write", self._toggle)
        entry.focus_set()
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        parent.wait_window(self)

    def _toggle(self, *_args):
        state = "normal" if self.confirm_var.get().strip() == "APPLY" else "disabled"
        self.apply_button.configure(state=state)

    def _apply(self):
        self.result = True
        self.destroy()


class DeploymentEditor(ProjectEditor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._deployment_busy = False

    def _build_menu(self):
        super()._build_menu()
        menu = self.nametowidget(self.cget("menu"))
        deploy = tk.Menu(menu, tearoff=False)
        deploy.add_command(label="Preview live diff...", command=self.remote_preview)
        deploy.add_command(label="Apply to live TRB...", command=self.remote_apply)
        deploy.add_separator()
        deploy.add_command(label="Rollback snapshot...", command=self.remote_rollback)
        menu.add_cascade(label="Deployment", menu=deploy)

    def _ssh_details(self):
        host = simpledialog.askstring(
            "TRB connection", "Host/IP:", initialvalue="10.33.22.1", parent=self
        )
        if not host:
            return None
        user = simpledialog.askstring(
            "TRB connection", "SSH username:", initialvalue="root", parent=self
        ) or "root"
        password = simpledialog.askstring(
            "TRB connection", "SSH password:", show="*", parent=self
        )
        if password is None:
            return None
        trust = messagebox.askyesno(
            "SSH host key",
            "If this host key is not already in your SSH known_hosts file, allow it for this connection?\n\n"
            "Choose No for strict host-key verification.",
            parent=self,
        )
        return host, user, password, trust

    def _validated_generated(self):
        messages = validate_project(self.project)
        errors = [m.message for m in messages if m.level == "error"]
        if errors:
            messagebox.showerror(
                "Validation failed",
                "The project cannot be deployed until these errors are fixed:\n\n- "
                + "\n- ".join(errors),
                parent=self,
            )
            return None
        try:
            return generate_uci(self.project)
        except Exception as exc:
            messagebox.showerror("Generation failed", str(exc), parent=self)
            return None

    def _start_background(self, worker, on_success, on_error, initial_status: str):
        """Run blocking network work off the Tk thread and marshal results back safely."""
        if self._deployment_busy:
            messagebox.showinfo(
                "Deployment busy",
                "Another live deployment operation is still running.",
                parent=self,
            )
            return False

        self._deployment_busy = True
        events: Queue = Queue()
        self.status.set(initial_status)

        def progress(message: str) -> None:
            events.put(("progress", message))

        def target() -> None:
            try:
                result = worker(progress)
            except Exception as exc:
                events.put(("error", exc))
            else:
                events.put(("success", result))

        Thread(target=target, daemon=True).start()

        def poll() -> None:
            try:
                while True:
                    kind, payload = events.get_nowait()
                    if kind == "progress":
                        self.status.set(str(payload))
                    elif kind == "success":
                        self._deployment_busy = False
                        on_success(payload)
                        return
                    elif kind == "error":
                        self._deployment_busy = False
                        on_error(payload)
                        return
            except Empty:
                pass
            self.after(100, poll)

        self.after(100, poll)
        return True

    def remote_preview(self):
        generated = self._validated_generated()
        if generated is None:
            return
        details = self._ssh_details()
        if details is None:
            return
        host, user, password, trust = details

        def worker(progress):
            progress(f"Connecting to {host}...")
            with SshSession(host, username=user, password=password, trust_new_host=trust) as session:
                progress(f"Reading live configuration from {host}...")
                current = read_remote_config(session)
            progress("Building live diff...")
            return render_diff(current, generated)

        def success(diff):
            if not diff:
                messagebox.showinfo(
                    "Live diff", "Live configuration already matches this project.", parent=self
                )
            else:
                TextWindow(self, f"Live diff - {host}", diff)
            self.status.set(f"Live preview complete for {host}")

        def failure(exc):
            self.status.set("Live preview failed")
            messagebox.showerror("Remote preview failed", str(exc), parent=self)

        self._start_background(worker, success, failure, f"Connecting to {host}...")

    def remote_apply(self):
        generated = self._validated_generated()
        if generated is None:
            return
        details = self._ssh_details()
        if details is None:
            return
        host, user, password, trust = details

        def read_worker(progress):
            progress(f"Connecting to {host}...")
            with SshSession(host, username=user, password=password, trust_new_host=trust) as session:
                progress(f"Reading live configuration from {host}...")
                current = read_remote_config(session)
            progress("Building live diff...")
            return current, render_diff(current, generated)

        def read_success(result):
            current, diff = result
            if not diff:
                messagebox.showinfo(
                    "Nothing to apply",
                    "Live configuration already matches this project.",
                    parent=self,
                )
                self.status.set("Nothing to apply")
                return

            confirm = DiffConfirmDialog(self, diff)
            if not confirm.result:
                self.status.set("Apply cancelled")
                return

            snapshot = new_snapshot_name()

            def apply_worker(progress):
                progress(f"Creating local backup {snapshot}...")
                local_backup = save_local_backup(current, Path("backups"), snapshot)
                progress(f"Connecting to {host} for deployment...")
                with SshSession(host, username=user, password=password, trust_new_host=trust) as session:
                    apply_generated(session, generated, snapshot=snapshot, progress=progress)
                return local_backup

            def apply_success(local_backup):
                messagebox.showinfo(
                    "Apply complete",
                    f"Configuration applied successfully.\n\n"
                    f"Local backup: {local_backup}\n"
                    f"Remote snapshot: {snapshot}\n\n"
                    f"Keep the snapshot name for rollback.",
                    parent=self,
                )
                self.status.set(f"Apply complete - snapshot {snapshot}")

            def apply_failure(exc):
                self.status.set("Apply failed")
                messagebox.showerror(
                    "Apply failed",
                    f"The deployment did not complete.\n\n{exc}\n\n"
                    "If a remote snapshot was created, use Rollback snapshot after checking the device.",
                    parent=self,
                )

            self._start_background(
                apply_worker,
                apply_success,
                apply_failure,
                f"Preparing deployment to {host}...",
            )

        def read_failure(exc):
            self.status.set("Apply failed before write")
            messagebox.showerror("Apply failed", str(exc), parent=self)

        self._start_background(read_worker, read_success, read_failure, f"Connecting to {host}...")

    def remote_rollback(self):
        details = self._ssh_details()
        if details is None:
            return
        host, user, password, trust = details
        snapshot = simpledialog.askstring(
            "Rollback snapshot",
            "Remote snapshot name (for example 20260818T090000Z):",
            parent=self,
        )
        if not snapshot:
            return
        if not messagebox.askyesno(
            "Confirm rollback",
            f"Restore snapshot {snapshot} on {host}?\n\n"
            "This will replace modbus_client and modbus_server and restart the Modbus services.",
            parent=self,
        ):
            return

        def worker(progress):
            progress(f"Connecting to {host}...")
            with SshSession(host, username=user, password=password, trust_new_host=trust) as session:
                rollback_snapshot(session, snapshot, progress=progress)

        def success(_result):
            self.status.set(f"Rollback complete - {snapshot}")
            messagebox.showinfo(
                "Rollback complete",
                f"Restored remote snapshot {snapshot} on {host}.",
                parent=self,
            )

        def failure(exc):
            self.status.set("Rollback failed")
            messagebox.showerror("Rollback failed", str(exc), parent=self)

        self._start_background(worker, success, failure, f"Connecting to {host}...")


def main() -> None:
    DeploymentEditor().mainloop()


if __name__ == "__main__":
    main()
