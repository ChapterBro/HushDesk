from __future__ import annotations
import sys
import json

from hushdesk.core.privacy_runtime import privacy_state
from hushdesk.tools.simregress import run_regression


def main(argv=None):
    state = privacy_state()
    ok_priv = all(
        [
            state.get("private_tmp") is True,
            state.get("deny_network") is True,
            state.get("disable_crashdialogs") is True,
        ]
    )
    reg_pass = run_regression()
    overall = ok_priv and reg_pass
    print(
        json.dumps(
            {
                "private_tmp": state.get("private_tmp"),
                "deny_network": state.get("deny_network"),
                "disable_crashdialogs": state.get("disable_crashdialogs"),
                "regression": "PASS" if reg_pass else "FAIL",
                "overall": "PASS" if overall else "FAIL",
            }
        )
    )
    sys.exit(0 if overall else 1)


if __name__ == "__main__":
    main(sys.argv[1:])
