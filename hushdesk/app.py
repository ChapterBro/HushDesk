"""Tkinter application entry point for HushDesk."""
from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox

import ttkbootstrap as ttk

from .core import audit, exporters
from .core.timeutil import default_audit_day
from .ui.theme import apply_dark_theme


class HushDeskApp(ttk.Window):
    def __init__(self) -> None:
        super().__init__(themename="darkly")
        self.title("HushDesk")
        self.geometry("900x640")
        apply_dark_theme(self)
        self.audit_date = default_audit_day()
        self.include_med_names = tk.BooleanVar(value=False)
        self._build_layout()

    def _build_layout(self) -> None:
        header = ttk.Frame(self, padding=20)
        header.pack(fill=tk.X)
        ttk.Label(header, text="HushDesk", font=("Segoe UI", 24)).pack(anchor=tk.W)
        ttk.Label(header, text="BP Holds", font=("Segoe UI", 14)).pack(anchor=tk.W)
        ttk.Label(header, text="Offline • CT", font=("Segoe UI", 10)).pack(anchor=tk.W)

        body = ttk.Frame(self, padding=20)
        body.pack(fill=tk.BOTH, expand=True)
        self.drop_label = ttk.Label(body, text="Drop MAR (PDF) or choose file", bootstyle="secondary")
        self.drop_label.pack(fill=tk.X, pady=10)
        controls = ttk.Frame(body)
        controls.pack(fill=tk.X, pady=10)
        self.auto_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(controls, text="Auto (Yesterday)", variable=self.auto_var, command=self._toggle_auto).pack(side=tk.LEFT)
        self.date_var = tk.StringVar(value=str(self.audit_date))
        self.date_entry = ttk.Entry(controls, textvariable=self.date_var, state="disabled", width=12)
        ttk.Label(controls, text="Date").pack(side=tk.LEFT, padx=(12, 4))
        self.date_entry.pack(side=tk.LEFT)

        ttk.Button(body, text="Run Audit", bootstyle="danger", command=self._run_audit).pack(pady=12)

        footer = ttk.Frame(body)
        footer.pack(fill=tk.X, pady=(40, 0))
        self.summary_var = tk.StringVar(value="Reviewed • Held • Compliant • Exceptions — badge: ")
        ttk.Label(footer, textvariable=self.summary_var).pack(anchor=tk.W)

        export_bar = ttk.Frame(body)
        export_bar.pack(fill=tk.X, pady=10)
        ttk.Button(export_bar, text="Save TXT (Room-only)", command=self._save_txt).pack(side=tk.LEFT, padx=5)
        ttk.Button(export_bar, text="Save JSON (Room-only)", command=self._save_json).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(export_bar, text="Include medication names", variable=self.include_med_names).pack(side=tk.LEFT, padx=10)

        ttk.Button(body, text="Purge Data", command=self._purge).pack(anchor=tk.E, pady=20)

        self.results = []
        self.meta = {}

    def _toggle_auto(self) -> None:
        if self.auto_var.get():
            self.audit_date = default_audit_day()
            self.date_var.set(str(self.audit_date))
            self.date_entry.configure(state="disabled")
        else:
            self.date_entry.configure(state="normal")

    def _confirm_names(self) -> bool:
        if not self.include_med_names.get():
            return False
        response = messagebox.askyesnocancel(
            "Include medication names",
            "Include medication names in the saved file?",
        )
        if response is None:
            raise exporters.ExportCancelled("cancelled")
        return response

    def _run_audit(self) -> None:
        file_path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if not file_path:
            return
        if not self.auto_var.get():
            try:
                self.audit_date = datetime.strptime(self.date_var.get(), "%Y-%m-%d").date()
            except ValueError:
                messagebox.showerror("Invalid date", "Enter date as YYYY-MM-DD")
                return
        else:
            self.audit_date = default_audit_day()
        audit_dt = datetime.combine(self.audit_date, datetime.min.time())
        results, meta = audit.run_audit(file_path, audit_dt)
        self.results = results
        self.meta = meta
        summary = meta.get("summary", {})
        badge = "OK" if summary.get("invariant_ok") else "MISMATCH"
        self.summary_var.set(
            f"Reviewed {summary.get('reviewed', 0)} • Held {summary.get('held', 0)} • Compliant {summary.get('compliant', 0)} • Exceptions {summary.get('exceptions', 0)} — badge: {badge}"
        )

    def _save(self, exporter) -> None:
        if not self.results:
            messagebox.showwarning("Nothing to export", "Run an audit first.")
            return
        include_names = False
        if self.include_med_names.get():
            include_names = self._confirm_names()
        path = filedialog.asksaveasfilename(defaultextension=".txt")
        if not path:
            return
        exporter(path, self.results, self.meta, include_names=include_names)

    def _save_txt(self) -> None:
        self._save(lambda p, results, meta, include_names=False: exporters.export_txt(p, results, include_names=include_names))

    def _save_json(self) -> None:
        self._save(lambda p, results, meta, include_names=False: exporters.export_json(p, results, meta, include_names=include_names))

    def _purge(self) -> None:
        response = messagebox.askokcancel("Purge Data", "Remove temp files, diagnostics, and recent list?")
        if response:
            self.results = []
            self.meta = {}
            self.summary_var.set("Reviewed • Held • Compliant • Exceptions — badge: ")


def main() -> None:
    app = HushDeskApp()
    app.mainloop()


if __name__ == "__main__":  # pragma: no cover
    main()
