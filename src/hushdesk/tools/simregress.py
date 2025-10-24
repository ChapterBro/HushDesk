from __future__ import annotations
from typing import Dict, Tuple

from hushdesk.core.engine import run_sim

Expected = Tuple[int, int, int, int, int]

CASES: Dict[str, Expected] = {
    "fixtures/sample_sim_bridgeman_10-24-2025_dual.json": (2, 2, 0, 0, 0),
    "fixtures/sample_sim_bridgeman_10-25-2025_dcd_held.json": (3, 0, 1, 1, 1),
    "fixtures/sample_sim_bridgeman_10-26-2025_given_variants.json": (2, 1, 0, 1, 0),
}


def counts_for(path: str) -> Expected:
    payload = run_sim.run_from_fixture(path)
    summary = payload["summary"]
    return (
        int(summary.get("reviewed", 0)),
        int(summary.get("hold_miss", 0)),
        int(summary.get("held_ok", 0)),
        int(summary.get("compliant", 0)),
        int(summary.get("dcd", 0)),
    )


def run_regression() -> bool:
    failed = []
    for path, exp in CASES.items():
        got = counts_for(path)
        print(
            f"{path}\n  expected: Reviewed={exp[0]} HM={exp[1]} HeldOK={exp[2]} Compliant={exp[3]} DCD={exp[4]}"
        )
        print(
            f"  got:      Reviewed={got[0]} HM={got[1]} HeldOK={got[2]} Compliant={got[3]} DCD={got[4]}"
        )
        if got != exp:
            failed.append((path, exp, got))
    if failed:
        print("\nREGRESSION: FAIL")
        for path, exp, got in failed:
            print(f"- {path}: expected {exp}, got {got}")
        return False
    print("\nREGRESSION: PASS")
    return True
