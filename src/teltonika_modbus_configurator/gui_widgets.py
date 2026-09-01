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


def attach_overlay_scrollbars(tree) -> None:
    """Add auto-hiding scrollbars to an already-packed Treeview.

    Existing main-window tabs build Treeviews directly into their parent frames.
    Re-parenting those widgets is not possible in Tk, so v0.5 overlays the bars on
    the right/bottom edge and only shows them when that axis can actually scroll.
    """
    parent = tree.master
    yscroll = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
    xscroll = ttk.Scrollbar(parent, orient="horizontal", command=tree.xview)
    state = {"y": False, "x": False}

    def place_y():
        yscroll.place(in_=tree, relx=1.0, x=-16, rely=0.0, relheight=1.0)
        yscroll.lift()
        state["y"] = True

    def place_x():
        xscroll.place(in_=tree, relx=0.0, rely=1.0, y=-16, relwidth=1.0)
        xscroll.lift()
        state["x"] = True

    def set_y(first, last):
        yscroll.set(first, last)
        needed = not (float(first) <= 0.0 and float(last) >= 1.0)
        if needed and not state["y"]:
            place_y()
        elif not needed and state["y"]:
            yscroll.place_forget()
            state["y"] = False

    def set_x(first, last):
        xscroll.set(first, last)
        needed = not (float(first) <= 0.0 and float(last) >= 1.0)
        if needed and not state["x"]:
            place_x()
        elif not needed and state["x"]:
            xscroll.place_forget()
            state["x"] = False

    tree.configure(yscrollcommand=set_y, xscrollcommand=set_x)
    tree._tmc_scrollbars = (yscroll, xscroll, state)  # type: ignore[attr-defined]
