"""Reusable Tkinter widgets/helpers shared by large project tables."""

from __future__ import annotations

from tkinter import ttk


class AutoHideScrollbar(ttk.Scrollbar):
    """Scrollbar that only shows itself when the associated view can scroll."""

    def __init__(self, master, *, orient: str, command):
        super().__init__(master, orient=orient, command=command)
        self._grid_options: dict[str, object] | None = None

    def grid(self, **kwargs):  # type: ignore[override]
        self._grid_options = dict(kwargs)
        return super().grid(**kwargs)

    def set(self, first, last):  # type: ignore[override]
        first_f = float(first)
        last_f = float(last)
        if first_f <= 0.0 and last_f >= 1.0:
            super().grid_remove()
        elif self._grid_options is not None:
            super().grid()
        super().set(first, last)


def tree_with_scrollbars(parent, *, columns, show="headings", selectmode="browse"):
    """Return ``(frame, tree)`` with auto-hiding vertical/horizontal scrollbars."""
    frame = ttk.Frame(parent)
    tree = ttk.Treeview(frame, columns=columns, show=show, selectmode=selectmode)
    yscroll = AutoHideScrollbar(frame, orient="vertical", command=tree.yview)
    xscroll = AutoHideScrollbar(frame, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(0, weight=1)
    tree.grid(row=0, column=0, sticky="nsew")
    yscroll.grid(row=0, column=1, sticky="ns")
    xscroll.grid(row=1, column=0, sticky="ew")
    return frame, tree
