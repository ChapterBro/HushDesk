from __future__ import annotations

import importlib
import warnings
from types import ModuleType
from typing import Optional

_WARNING_PATTERN = r"builtin type .* has no __module__ attribute"


def import_fitz(*, optional: bool = False) -> Optional[ModuleType]:
    """
    Import PyMuPDF (`fitz`) while silencing the noisy SWIG deprecation warnings.

    When ``optional`` is True, missing modules or import errors return ``None``
    so callers can gracefully fall back to other engines.
    """
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=_WARNING_PATTERN, category=DeprecationWarning)
        try:
            module = importlib.import_module("fitz")
        except Exception:
            if optional:
                return None
            raise
    return module


__all__ = ["import_fitz"]

