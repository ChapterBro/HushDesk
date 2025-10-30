import os, sys, importlib, traceback
from multiprocessing import freeze_support

def _prefer(names, module):
    for n in names:
        obj = getattr(module, n, None)
        if callable(obj):
            return obj
    return None

def _go_exe_dir():
    try:
        base = getattr(sys, "_MEIPASS", None) or os.path.dirname(sys.executable)
        if base and os.path.isdir(base):
            os.chdir(base)
    except Exception:
        pass

def _secure_defaults():
    try:
        from hushdesk.core.privacy_runtime import secure_defaults  # optional
        secure_defaults()
    except Exception:
        pass

def launch():
    _go_exe_dir()
    _secure_defaults()

    # Try canonical module then common fallbacks
    module = None
    for modname in ("hushdesk.ui.app", "hushdesk.ui", "hushdesk.ui.main", "hushdesk.ui.app_main"):
        try:
            module = importlib.import_module(modname)
            break
        except Exception:
            module = None
    if module is None:
        raise RuntimeError("Unable to import a UI module (tried hushdesk.ui.app, hushdesk.ui, hushdesk.ui.main, hushdesk.ui.app_main).")

    # Prefer explicit functions
    fn = _prefer(("run", "run_ui", "main", "start", "launch", "entry"), module)
    if fn:
        return fn()

    # Fallback to App.run/mainloop
    App = getattr(module, "App", None)
    if App:
        inst = App()
        if callable(getattr(inst, "run", None)):
            return inst.run()
        if callable(getattr(inst, "mainloop", None)):
            inst.mainloop()
            return 0

    raise RuntimeError("No GUI entry found. Looked for: run, run_ui, main, start, launch, entry, App.run, App.mainloop.")

def _fail_dialog(exc: BaseException):
    # Persist a crash log
    try:
        ad = os.getenv("LOCALAPPDATA", "") or os.getcwd()
        logdir = os.path.join(ad, "HushDesk")
        os.makedirs(logdir, exist_ok=True)
        with open(os.path.join(logdir, "last_gui_error.txt"), "w", encoding="utf-8") as f:
            f.write("HushDesk GUI failed to start:\n\n")
            f.write("Exception: " + repr(exc) + "\n\n")
            f.write("Traceback:\n" + "".join(traceback.format_exc()))
    except Exception:
        pass
    # Show a message box even in --noconsole builds
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk(); root.withdraw()
        messagebox.showerror("HushDesk", f"Unable to start the UI:\n{exc}")
    except Exception:
        pass

if __name__ == "__main__":
    freeze_support()
    try:
        rc = launch()
        sys.exit(0 if rc is None else int(rc))
    except SystemExit:
        raise
    except Exception as e:
        _fail_dialog(e)
        sys.exit(1)
