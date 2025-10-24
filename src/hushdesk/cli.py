from __future__ import annotations
import argparse, datetime as dt
from dataclasses import asdict
from pathlib import Path
from typing import List, Dict, Tuple

import sys

from hushdesk.core.privacy_runtime import lock_down_process, selfcheck_summary
from hushdesk.core import building_master as BM
from hushdesk.core.engine import run_sim
from hushdesk.core.engine.decide import DecisionRecord
from hushdesk.core.export.checklist_render import write_txt
from hushdesk.core.export.json_writer import write_records, file_sha256
from hushdesk.win_entry.self_check import main as self_check_main

DecisionLineSections = Dict[str, List[str]]

def _us_date(s: str) -> str:
    return dt.datetime.strptime(s, "%m-%d-%Y").strftime("%m-%d-%Y")

def _fmt_hold_phrase(rule: Dict | None) -> str | None:
    if not rule:
        return None
    metric = (rule.get("metric") or rule.get("type") or "").upper()
    op = rule.get("op")
    threshold = rule.get("threshold")
    if not (metric and op and threshold is not None):
        return None
    return f"Hold if {metric} {op} {threshold}"

def _first_rule(record: DecisionRecord) -> Dict | None:
    if record.rule:
        return record.rule
    src = record.source or {}
    rules = src.get("rules") or []
    return rules[0] if rules else None

def _format_vitals(record: DecisionRecord) -> str:
    pieces: List[str] = []
    sbp = record.measured.get("sbp")
    dbp = record.measured.get("dbp")
    hr = record.measured.get("hr")
    if sbp is not None and dbp is not None:
        pieces.append(f"BP {sbp}/{dbp}")
    elif sbp is not None:
        pieces.append(f"SBP {sbp}")
    if hr is not None:
        pieces.append(f"HR {hr}")
    return "; ".join(pieces)

def _format_given(record: DecisionRecord) -> str:
    admin = record.admin or {}
    if not admin.get("given"):
        return ""
    if admin.get("time"):
        return f"given {admin['time']}"
    return "given"

def _render_line(record: DecisionRecord) -> str:
    rule = _first_rule(record)
    hold_phrase = _fmt_hold_phrase(rule)
    pieces: List[str] = []

    if record.decision == "DC'D":
        if hold_phrase:
            pieces.append(hold_phrase)
        vitals = _format_vitals(record)
        if vitals:
            pieces.append(vitals)
        pieces.append("X in due cell")
    elif record.decision == "HELD-APPROPRIATE":
        if hold_phrase:
            pieces.append(hold_phrase)
        vitals = _format_vitals(record)
        if vitals:
            pieces.append(vitals)
        code = record.admin.get("chart_code")
        if code is not None:
            pieces.append(f"code {code}")
    elif record.decision == "COMPLIANT":
        if hold_phrase:
            pieces.append(hold_phrase)
        vitals = _format_vitals(record)
        if vitals:
            pieces.append(vitals)
        given = _format_given(record)
        if given:
            pieces.append(given)
    else:  # HOLD-MISS
        if hold_phrase:
            pieces.append(hold_phrase)
        vitals = _format_vitals(record)
        if vitals:
            pieces.append(vitals)
        given = _format_given(record)
        if given:
            pieces.append(given)

    phrase = "; ".join([p for p in pieces if p])
    return f"{record.room} ({record.time_track}) — {phrase}"

def _collect_sections(records: List[DecisionRecord]) -> Tuple[Dict[str, int], DecisionLineSections]:
    counts = {"reviewed": 0, "hold_miss": 0, "held_ok": 0, "compliant": 0, "dcd": 0}
    sections: DecisionLineSections = {
        "HOLD-MISS": [],
        "HELD-APPROPRIATE": [],
        "COMPLIANT": [],
        "DC'D": [],
    }
    for rec in records:
        counts["reviewed"] += 1
        line = _render_line(rec)
        if rec.decision == "HOLD-MISS":
            counts["hold_miss"] += 1
            sections["HOLD-MISS"].append(line)
        elif rec.decision == "HELD-APPROPRIATE":
            counts["held_ok"] += 1
            sections["HELD-APPROPRIATE"].append(line)
        elif rec.decision == "COMPLIANT":
            counts["compliant"] += 1
            sections["COMPLIANT"].append(line)
        elif rec.decision == "DC'D":
            counts["dcd"] += 1
            sections["DC'D"].append(line)
    return counts, sections

def _records_for_rooms(
    *,
    mar_path: str,
    date_col_index: int,
    date_str: str,
    hall: str,
    rooms: List[str],
    pages: List[int] | None,
) -> List[DecisionRecord]:
    from hushdesk.core.engine import run_pdf  # Lazy import; requires PyMuPDF only when PDF path used
    all_records: List[DecisionRecord] = []
    for room in rooms:
        recs = run_pdf.extract_records_for_date(
            pdf_path=mar_path,
            date_col_index=date_col_index,
            date_str_us=date_str,
            hall=hall,
            room=room,
            page_indices=pages,
        )
        all_records.extend(recs)
    return all_records

def _sanitize_for_json(rec: DecisionRecord) -> Dict:
    data = asdict(rec)
    src = data.get("source") or {}
    data["source"] = {"page": src.get("page"), "col": src.get("col")}
    return data

def _cmd_master_info(_: argparse.Namespace) -> None:
    print("HushDesk — Building Master")
    print("Halls:", ", ".join(BM.halls()))
    h0 = BM.halls()[0]
    print(f"Sample rooms in {h0}:", ", ".join(sorted(list(BM.rooms_in_hall(h0)))[:6]))

def _cmd_bp_audit(args: argparse.Namespace) -> None:
    from hushdesk.core.engine import run_pdf

    date_str = _parse_date_us(args.date)
    hall = args.hall or ""
    payload = run_pdf.run({
        "mar_path": args.mar,
        "date_str": date_str,
        "hall": hall,
        "room_filters": args.rooms or [],
        "emit_json": bool(args.emit_json),
        "out_txt": args.out or "",
        "summary_only": bool(args.summary_only),
        "tz": "America/Chicago",
    })
    summary = payload["summary"]
    print(
        f"Reviewed: {summary['reviewed']} | Hold-Miss: {summary['hold_miss']} | "
        f"Held-OK: {summary['held_ok']} | Compliant: {summary['compliant']} | DC'D: {summary['dcd']}"
    )
    if summary["hold_miss"] > 0:
        raise SystemExit(2)
    raise SystemExit(0)

def _cmd_bp_audit_sim(args: argparse.Namespace) -> None:
    payload = run_sim.run_from_fixture(args.fixture)
    summary = payload["summary"]
    sections = payload["sections"]
    header = payload["header"]

    if args.summary_only:
        print(
            f"Reviewed: {summary['reviewed']} | Hold-Miss: {summary['hold_miss']} | "
            f"Held-Appropriate: {summary['held_ok']} | Compliant: {summary['compliant']} | "
            f"DC'D: {summary['dcd']}"
        )
        if summary["hold_miss"] > 0:
            sys.exit(2)
        return

    hall_slug = (header.get("hall", "") or "").lower().replace(" ", "_")
    out_txt = args.out or f"bp_audit_{header.get('date_str','')}_{hall_slug}_sim.txt"
    write_txt(out_txt, header, summary, sections)

    json_path = "disabled"
    if args.emit_json:
        json_path = out_txt.replace(".txt", ".json")
        meta = {"fixture_file": header.get("source") or Path(args.fixture).name}
        records = [asdict(r) for r in payload.get("records", [])]
        write_records(json_path, records, meta)

    print("TXT:", out_txt)
    print("JSON:", json_path)

    if summary["hold_miss"] > 0:
        sys.exit(2)

def _cmd_privacy_selfcheck(_: argparse.Namespace) -> None:
    print("HushDesk privacy:", selfcheck_summary())


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="hushdesk")
    ap.add_argument("--allow-network", action="store_true", help="Allow network (default: disabled)")
    ap.add_argument("--no-private-tmp", action="store_true", help="Disable private TMP (default: enabled)")
    ap.add_argument("--allow-crashdialogs", action="store_true", help="Allow OS crash dialogs (default: disabled)")
    sp = ap.add_subparsers(dest="cmd")
    sp.add_parser("master-info").set_defaults(func=_cmd_master_info)
    p = sp.add_parser("bp-audit", help="Run BP audit on a MAR PDF")
    p.add_argument("--mar", required=True, help="Path to MAR PDF (single hall)")
    p.add_argument("--date", required=True, help="MM-DD-YYYY")
    p.add_argument("--hall", required=True, choices=BM.halls())
    p.add_argument("--room", required=False, help="Specific room to audit (defaults to hall)")
    p.add_argument("--pages", required=False, help="Comma separated page numbers (1-indexed)")
    p.add_argument("--out", required=False, help="Output TXT path")
    p.add_argument("--emit-json", action="store_true", help="Also write JSON twin")
    p.add_argument("--summary-only", action="store_true", help="Print counts only (no TXT/JSON files)")
    q = sp.add_parser("bp-audit-sim", help="Run BP audit from a JSON simulation fixture (no PDF)")
    q.add_argument("--fixture", required=True, help="Path to simulation JSON")
    q.add_argument("--out", required=False, help="Output TXT path")
    q.add_argument("--emit-json", action="store_true", help="Also write JSON twin")
    q.add_argument("--summary-only", action="store_true", help="Print counts only (no TXT/JSON files)")
    sp.add_parser("privacy-selfcheck", help="Print runtime privacy toggles and exit").set_defaults(func=_cmd_privacy_selfcheck)
    sp.add_parser("self-check", help="Run privacy + regression self-check").set_defaults(func=lambda _args: self_check_main([]))

    p.set_defaults(func=_cmd_bp_audit)
    q.set_defaults(func=_cmd_bp_audit_sim)

    args = ap.parse_args(argv)
    if not hasattr(args, "func"):
        ap.print_help()
        return
    lock_down_process(
        private_tmp=not args.no_private_tmp,
        deny_network=not args.allow_network,
        disable_crash=not args.allow_crashdialogs,
    )
    args.func(args)

if __name__ == "__main__":
    main()
