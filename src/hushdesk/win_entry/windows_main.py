from __future__ import annotations
import sys

from hushdesk.core.privacy_runtime import lock_down_process

try:
    from tools.windows.privacy_runtime_win import (
        apply_private_tmp,
        deny_network_globally,
        suppress_crash_dialogs,
    )
except Exception:  # pragma: no cover
    from hushdesk_win_privacy import (  # type: ignore
        apply_private_tmp,
        deny_network_globally,
        suppress_crash_dialogs,
    )


def _windows_hardening() -> None:
    try:
        apply_private_tmp()
    except Exception:
        pass
    try:
        deny_network_globally()
    except Exception:
        pass
    try:
        suppress_crash_dialogs()
    except Exception:
        pass


def main() -> None:
    lock_down_process(allow_network=False, use_private_tmp=True, suppress_crashdialogs=True)
    _windows_hardening()
    from hushdesk.cli import main as cli_main

    cli_main(sys.argv[1:])


if __name__ == "__main__":  # pragma: no cover
    main()
