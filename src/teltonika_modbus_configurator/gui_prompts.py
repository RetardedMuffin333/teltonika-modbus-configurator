"""Foreground-safe Tk prompts for live connection workflows."""

from __future__ import annotations

import tkinter as tk
from tkinter import simpledialog


def _focus_active_modal(parent) -> None:
    try:
        dialog = parent.grab_current()
        if dialog is None:
            return
        dialog.deiconify()
        dialog.lift()
        dialog.attributes("-topmost", True)
        dialog.after(150, lambda: _clear_topmost(dialog))
        focused = dialog.focus_get()
        if focused is not None:
            focused.focus_force()
        else:
            dialog.focus_force()
    except tk.TclError:
        return


def _clear_topmost(dialog) -> None:
    try:
        if dialog.winfo_exists():
            dialog.attributes("-topmost", False)
    except tk.TclError:
        return


def askstring_foreground(parent, title: str, prompt: str, **options):
    """Show ``askstring`` as a foreground modal with keyboard focus on Windows."""
    try:
        top = parent.winfo_toplevel()
        top.deiconify()
        top.lift()
        top.focus_force()
        top.update_idletasks()
        top.after(40, lambda: _focus_active_modal(parent))
    except tk.TclError:
        pass
    return simpledialog.askstring(title, prompt, parent=parent, **options)
