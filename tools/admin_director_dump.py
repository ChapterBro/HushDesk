from __future__ import annotations
import pkgutil
from hushdesk.core import building_master as BM
from hushdesk.core.constants import ALLOWED_HELD_CODES, GIVEN_GLYPHS


def main() -> None:
    print("HushDesk — Administrative Director digest")
    print("halls:", ", ".join(BM.halls()))
    print("allowed_held_codes:", sorted(ALLOWED_HELD_CODES))
    print("given_glyphs:", "".join(GIVEN_GLYPHS))
    print("modules under core/:")
    for m in sorted([m.name for m in pkgutil.iter_modules(["src/hushdesk/core"]) ]):
        print(" -", m)


if __name__ == "__main__":
    main()
