"""Dialog helpers centralised for reuse."""
from __future__ import annotations

from tkinter import messagebox

from ..core import exporters


def confirm_med_names() -> bool:
    response = messagebox.askyesnocancel(
        "Include medication names",
        "Include medication names in the saved file?",
    )
    if response is None:
        raise exporters.ExportCancelled("cancelled")
    return response


def confirm_purge() -> bool:
    return messagebox.askokcancel(
        "Purge Data",
        "Remove temp files, diagnostics, and recent list?",
    )
