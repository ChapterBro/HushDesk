from __future__ import annotations
import sys
from hushdesk.tools.simregress import run_regression


def main() -> int:
    return 0 if run_regression() else 1


if __name__ == "__main__":
    sys.exit(main())
