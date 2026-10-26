"""Windowed portable entry point, including a frozen-build smoke check."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys


def configure_logging() -> Path:
    folder = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Teltonika Modbus Configurator" / "logs"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "application.log"
    handler = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger = logging.getLogger("tmc.portable")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    return path


def smoke_test() -> None:
    import tkinter as tk
    import paramiko
    import requests
    import xlrd
    import openpyxl
    import yaml
    from io import BytesIO
    from teltonika_modbus_configurator.gui_v08 import V08ProjectEditor
    from teltonika_modbus_configurator.loader import load_project
    from teltonika_modbus_configurator.validator import validate_project

    workbook = openpyxl.Workbook()
    workbook.active["A1"] = "portable"
    stream = BytesIO()
    workbook.save(stream)
    stream.seek(0)
    assert openpyxl.load_workbook(stream).active["A1"].value == "portable"
    assert yaml.safe_load("portable: true")["portable"] is True
    assert requests.certs.where()
    paramiko.Ed25519Key
    xlrd.open_workbook
    # Construct the real editor to catch missing Tcl/Tk resources and GUI imports.
    app = V08ProjectEditor()
    app.withdraw()
    app.update_idletasks()
    app.destroy()
    root = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
    project = load_project(root / "examples" / "basic.yaml")
    assert not any(item.level == "error" for item in validate_project(project))


def main() -> int:
    path = None
    try:
        path = configure_logging()
        if "--smoke-test" in sys.argv:
            smoke_test()
            logging.getLogger("tmc.portable").info("Portable smoke test passed")
            return 0
        import tkinter as tk
        from tkinter import messagebox
        from teltonika_modbus_configurator.gui_v08 import main as gui_main

        def callback_error(self, exc, value, traceback):
            logging.getLogger("tmc.portable").error("GUI callback failed", exc_info=(exc, value, traceback))
            messagebox.showerror("Application error", f"An unexpected error occurred.\nDetails: {path}", parent=self)

        tk.Tk.report_callback_exception = callback_error
        gui_main()
        return 0
    except Exception:
        logging.getLogger("tmc.portable").exception("Application failed")
        if "--smoke-test" not in sys.argv:
            try:
                from tkinter import messagebox
                messagebox.showerror("Startup error", f"The application could not start.\nDetails: {path or 'log unavailable'}")
            except Exception:
                pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
