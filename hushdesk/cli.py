"""Command line interface for HushDesk."""
from __future__ import annotations

import argparse
import sys
from datetime import datetime

from .core import audit, exporters
from .core.timeutil import CT, default_audit_day


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="hushdesk")
    sub = parser.add_subparsers(dest="command", required=True)

    audit_parser = sub.add_parser("audit", help="Run an audit against a MAR PDF")
    audit_parser.add_argument("--in", dest="input_path", required=True)
    audit_parser.add_argument("--out", dest="output_path", required=True)
    audit_parser.add_argument("--date", dest="date", help="Audit date (YYYY-MM-DD)")
    audit_parser.add_argument("--include-med-names", action="store_true")
    return parser.parse_args(argv)


def _resolve_date(value: str | None) -> datetime:
    if value:
        try:
            parsed = datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError as exc:  # pragma: no cover
            raise SystemExit(f"Invalid date: {exc}")
        return datetime.combine(parsed, datetime.min.time(), tzinfo=CT)
    return datetime.combine(default_audit_day(), datetime.min.time(), tzinfo=CT)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    if args.command == "audit":
        audit_date = _resolve_date(args.date)
        try:
            results, meta = audit.run_audit(args.input_path, audit_date)
            exporters.export_json(args.output_path, results, meta, include_names=args.include_med_names)
        except exporters.ExportCancelled:
            print("Export cancelled", file=sys.stderr)
            return 1
        except Exception as exc:
            print(str(exc), file=sys.stderr)
            return 1
        return 0
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
