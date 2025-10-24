from __future__ import annotations
import os, socket, tempfile, uuid, sys, stat
from pathlib import Path
from typing import Optional

# --- State flags (for self-reporting) ---
_APPLIED = {
    "private_tmp": False,
    "deny_network": False,
    "disable_crashdialogs": False,
}

def _mkdir_0700(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)
    try:
        p.chmod(0o700)
    except Exception:
        pass  # best effort on platforms without chmod semantics

# --- Private TMP (POSIX + Windows) ---
def apply_private_tmp(base_dir: Optional[str] = None) -> str:
    """
    Create a private temp dir and force Python to use it.
    POSIX: ~/.hushdesk/tmp/<uuid> (0700)
    Windows: %LOCALAPPDATA%\HushDesk\tmp\<uuid> with restrictive ACLs (best effort here).
    Returns the path.
    """
    if base_dir:
        root = Path(base_dir)
    else:
        if os.name == "nt":
            local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
            root = Path(local) / "HushDesk" / "tmp"
        else:
            root = Path.home() / ".hushdesk" / "tmp"
    target = root / str(uuid.uuid4())
    try:
        _mkdir_0700(target)
    except PermissionError:
        fallback_root = Path.cwd() / ".hushdesk_tmp"
        target = fallback_root / str(uuid.uuid4())
        _mkdir_0700(target)

    # Point Python and most libs at this dir
    os.environ["TMPDIR"] = str(target)
    os.environ["TMP"] = str(target)
    os.environ["TEMP"] = str(target)
    tempfile.tempdir = str(target)
    _APPLIED["private_tmp"] = True
    return str(target)

# --- Deny network (monkey-patch socket.connect) ---
class _DenyConnect:
    def __call__(self, *a, **k):
        raise RuntimeError("Network disabled by HushDesk runtime")

def deny_network_globally() -> None:
    if _APPLIED["deny_network"]:
        return
    socket._orig_socket = socket.socket  # type: ignore[attr-defined]
    class NoNetSocket(socket._orig_socket):  # type: ignore[misc]
        def connect(self, *a, **k):
            raise RuntimeError("Network disabled by HushDesk runtime")
        def connect_ex(self, *a, **k):
            raise RuntimeError("Network disabled by HushDesk runtime")
    socket.socket = NoNetSocket  # type: ignore[assignment]
    _APPLIED["deny_network"] = True

# --- Disable crash dialogs (Windows best-effort; no-ops elsewhere) ---
def disable_crash_dialogs() -> None:
    if _APPLIED["disable_crashdialogs"]:
        return
    if os.name == "nt":
        try:
            import ctypes
            # WER flags: 0x1 = NO_UI, 0x2 = NO_REPORTING (per-process)
            WerSetFlags = ctypes.windll.kernel32.WerSetFlags
            WerSetFlags(ctypes.c_uint(0x1 | 0x2))
        except Exception:
            pass  # best effort
    _APPLIED["disable_crashdialogs"] = True


# --- File helpers (used by exporters) ---
def ensure_private_dir(dir_path: str) -> None:
    _mkdir_0700(Path(dir_path))


def secure_open_for_write(path: str) -> int:
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    mode = 0o600
    return os.open(path, flags, mode)

# --- Process lock-down: call from CLI early ---
def lock_down_process(
    *,
    private_tmp: bool = True,
    deny_network: bool = True,
    disable_crash: bool = True,
    allow_network: Optional[bool] = None,
    use_private_tmp: Optional[bool] = None,
    suppress_crashdialogs: Optional[bool] = None,
) -> dict:
    if allow_network is not None:
        deny_network = not allow_network
    if use_private_tmp is not None:
        private_tmp = use_private_tmp
    if suppress_crashdialogs is not None:
        disable_crash = suppress_crashdialogs

    path = None
    if private_tmp:
        path = apply_private_tmp()
    if deny_network:
        deny_network_globally()
    if disable_crash:
        disable_crash_dialogs()
    return {"private_tmp_path": path, **privacy_state()}

# --- Self-check helpers (used by CLI) ---
def selfcheck_summary() -> str:
    return f"private_tmp={_APPLIED['private_tmp']} deny_network={_APPLIED['deny_network']} disable_crashdialogs={_APPLIED['disable_crashdialogs']}"


def privacy_state() -> dict:
    return dict(_APPLIED)
