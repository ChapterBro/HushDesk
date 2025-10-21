"""UI theming helpers for the silent secretary aesthetic."""
from __future__ import annotations

import ttkbootstrap as ttk

_BG = "#121212"
_SURFACE = "#1E1E1E"
_TEXT = "#E6E6E6"
_LINES = "#2A2A2A"
_ACCENT = "#D32F2F"


def apply_dark_theme(window: ttk.Window) -> None:
    style = ttk.Style()
    style.configure("TFrame", background=_BG)
    style.configure("TLabel", background=_BG, foreground=_TEXT, font=("Segoe UI", 11))
    style.configure("TButton", font=("Segoe UI", 14))
    style.configure("TCheckbutton", background=_BG, foreground=_TEXT, font=("Segoe UI", 11))
    window.configure(background=_BG)
