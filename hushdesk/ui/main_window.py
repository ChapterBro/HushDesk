"""Main window components extracted for clarity."""
from __future__ import annotations

import tkinter as tk
import ttkbootstrap as ttk

from .theme import apply_dark_theme


class MainWindow(ttk.Frame):
    def __init__(self, master: ttk.Window) -> None:
        super().__init__(master)
        apply_dark_theme(master)
        self.pack(fill=tk.BOTH, expand=True)
