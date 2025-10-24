from __future__ import annotations
import sys
from hushdesk.core.engine.run_sim import run_fixture, load_fixture


def _dose_count_from_fixture(fx: dict) -> int:
    n = 0
    for row in fx.get("rows", []):
        if not row.get("rules"):
            continue
        if "AM" in row:
            n += 1
        if "PM" in row:
            n += 1
    return n


def main(path: str) -> None:
    fx = load_fixture(path)
    recs = run_fixture(path)

    reviewed = _dose_count_from_fixture(fx)
    counts = {"hold_miss": 0, "held_ok": 0, "compliant": 0, "dcd": 0}

    for r in recs:
        if r.decision == "HOLD-MISS":
            counts["hold_miss"] += 1
        elif r.decision == "HELD-APPROPRIATE":
            counts["held_ok"] += 1
        elif r.decision == "COMPLIANT":
            counts["compliant"] += 1
        elif r.decision == "DC'D":
            counts["dcd"] += 1

    print(f"Fixture: {fx['meta']['date']} {fx['meta']['hall']}")
    print(
        f"Reviewed: {reviewed} | Hold-Miss: {counts['hold_miss']} | "
        f"Held-Appropriate: {counts['held_ok']} | Compliant: {counts['compliant']} | DC'D: {counts['dcd']}"
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python tools/simcheck.py <fixture.json>")
        sys.exit(2)
    main(sys.argv[1])
