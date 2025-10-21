"""BP Holds tab implementation."""
from __future__ import annotations

import tkinter as tk
import ttkbootstrap as ttk


class BPTab(ttk.Frame):
    def __init__(self, master: ttk.Notebook) -> None:
        super().__init__(master)
        ttk.Label(self, text="BP Holds").pack(anchor=tk.W)
