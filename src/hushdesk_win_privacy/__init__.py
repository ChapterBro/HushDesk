from __future__ import annotations
import os
import ctypes
import socket
import uuid
from pathlib import Path
from typing import Optional


def _lockdown_acl_win(path: Path) -> None:
    try:
        os.system(f'icacls "{path}" /inheritance:r >NUL 2>NUL')
        os.system(f'icacls "{path}" /grant:r Administrators:(OI)(CI)(F) SYSTEM:(OI)(CI)(F) >NUL 2>NUL')
    except Exception:
        pass


def apply_private_tmp() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "HushDesk" / "tmp"
    target = root / str(uuid.uuid4())
    target.mkdir(parents=True, exist_ok=True)
    _lockdown_acl_win(root)
    _lockdown_acl_win(target)
    os.environ["TMP"] = str(target)
    os.environ["TEMP"] = str(target)
    try:
        import tempfile
        tempfile.tempdir = str(target)
    except Exception:
        pass
    return target


class _DenyConnect:
    def __call__(self, *args, **kwargs):
        raise OSError("Network disabled by HushDesk runtime policy.")


def deny_network_globally():
    socket.socket.connect = _DenyConnect()  # type: ignore[attr-defined]


def suppress_crash_dialogs():
    try:
        flags = 0x2  # DontShowUI
        ctypes.windll.kernel32.WerSetFlags(flags)  # type: ignore[attr-defined]
    except Exception:
        pass
