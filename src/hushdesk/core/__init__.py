from __future__ import annotations

import warnings

_WARNING_PATTERN = r"builtin type .* has no __module__ attribute"

# Ensure optional MuPDF imports inside hushdesk.core submodules do not spam
# DeprecationWarnings when the SWIG bindings register helper types.
warnings.filterwarnings(
    "ignore",
    message=_WARNING_PATTERN,
    category=DeprecationWarning,
)

