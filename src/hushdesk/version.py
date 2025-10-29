from __future__ import annotations

import os

try:
    from importlib.metadata import PackageNotFoundError, version as pkg_version
except ImportError:  # pragma: no cover - fallback for older runtimes
    pkg_version = None

    class PackageNotFoundError(Exception):
        pass


def detect_version() -> str:
    env = os.environ.get("HUSHDESK_VERSION")
    if env:
        return env
    if pkg_version is not None:
        try:
            return pkg_version("hushdesk")
        except PackageNotFoundError:
            pass
    return "0.0.0"


APP_VERSION = detect_version()

