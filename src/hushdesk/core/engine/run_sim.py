from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, List, Tuple

from hushdesk.core.engine.decide import DecisionRecord, decide_due, CellTokens
from hushdesk.core.rules.holds import Rule
from hushdesk.core import building_master as BM
from hushdesk.ui.util import summarize_counts


def _lines_for_groups(records: List[DecisionRecord]) -> Dict[str, List[str]]:
    groups = {"HOLD-MISS": [], "HELD-APPROPRIATE": [], "COMPLIANT": [], "DC'D": []}
    for r in records:
        room = r.room
        track = r.time_track
        if r.decision == "HOLD-MISS":
            rule = r.rule or {}
            metric = rule.get("type") or rule.get("metric") or ""
            op = rule.get("op", "")
            threshold = rule.get("threshold", "")
            measured = r.measured or {}
            sbp = measured.get("sbp")
            dbp = measured.get("dbp")
            hr = measured.get("hr")
            if sbp is not None and dbp is not None:
                groups["HOLD-MISS"].append(
                    f"{room} ({track}) — Hold if {metric} {op} {threshold}; BP {sbp}/{dbp}"
                )
            elif hr is not None:
                groups["HOLD-MISS"].append(
                    f"{room} ({track}) — Hold if {metric} {op} {threshold}; HR {hr}"
                )
            else:
                groups["HOLD-MISS"].append(
                    f"{room} ({track}) — Hold if {metric} {op} {threshold}"
                )
        elif r.decision == "HELD-APPROPRIATE":
            code = r.admin.get("chart_code") if r.admin else None
            suffix = f"code {code}" if code is not None else "code"
            groups["HELD-APPROPRIATE"].append(f"{room} ({track}) — {suffix}")
        elif r.decision == "COMPLIANT":
            groups["COMPLIANT"].append(f"{room} ({track}) — ✓")
        elif r.decision == "DC'D":
            groups["DC'D"].append(f"{room} ({track}) — X in due cell")
    return groups


def _preview_txt(header: Dict, summary: Dict, sections: Dict[str, List[str]]) -> str:
    from datetime import datetime, timezone, timedelta

    lines: List[str] = []
    lines.append(f"Date: {header.get('date_str','')}")
    lines.append(f"Hall: {header.get('hall','')}")
    src = header.get("source")
    if src:
        lines.append(f"Source: {src}")
    lines.append("")
    lines.append(f"Reviewed: {summary['reviewed']}")
    lines.append(f"Hold-Miss: {summary['hold_miss']}")
    lines.append(f"Held-Appropriate: {summary['held_ok']}")
    lines.append(f"Compliant: {summary['compliant']}")
    lines.append(f"DC'D: {summary['dcd']}")
    lines.append("")
    for title in ("HOLD-MISS", "HELD-APPROPRIATE", "COMPLIANT", "DC'D"):
        items = sections.get(title, []) or []
        if not items:
            continue
        lines.append(title)
        lines.extend(items)
        lines.append("")
    central = datetime.now(tz=timezone(timedelta(hours=-5))).strftime("%m-%d-%Y %H:%M")
    lines.append(f"Generated: {central} (Central)")
    return "\n".join(lines) + "\n"


def build_payload(records: List[DecisionRecord], *, header_meta: Dict, dose_total: int | None = None) -> Dict:
    summary = summarize_counts(records)
    if dose_total is not None:
        summary["reviewed"] = dose_total
    groups = _lines_for_groups(records)
    sections = {k: list(v) for k, v in groups.items()}
    violations = sections.get("HOLD-MISS", [])
    header = {
        "date_str": header_meta.get("date_str", ""),
        "hall": header_meta.get("hall", ""),
        "source": header_meta.get("source", ""),
    }
    payload = {
        "header": header,
        "summary": summary,
        "sections": sections,
        "groups": groups,
        "violations": violations,
        "rooms": sorted({r.room for r in records}),
        "txt_preview": _preview_txt(header, summary, sections),
        "pages": int(header_meta.get("pages", 1) or 1),
        "records": records,
    }
    return payload


def _decision_from_dict(item: Dict) -> DecisionRecord:
    return DecisionRecord(
        room=item.get("room", ""),
        hall=item.get("hall", ""),
        date=item.get("date", ""),
        time_track=item.get("time_track", "AM"),
        reviewed=bool(item.get("reviewed", True)),
        decision=item.get("decision"),
        rule=item.get("rule"),
        measured=item.get("measured", {}),
        admin=item.get("admin", {}),
        notes=item.get("notes", ""),
        source=item.get("source", {}),
    )


def _dose_total_from_rows(rows: List[Dict]) -> int:
    total = 0
    for row in rows:
        if not row.get("rules"):
            continue
        if "AM" in row:
            total += 1
        if "PM" in row:
            total += 1
    return total


def _records_from_rows(data: Dict) -> Tuple[List[DecisionRecord], Dict, int]:
    meta = data.get("meta", {})
    date = meta.get("date", "")
    hall_raw = meta.get("hall", "")
    hall = hall_raw
    if hall_raw:
        try:
            hall = BM.normalize_hall(hall_raw)
        except Exception:
            hall = hall_raw
    rows = data.get("rows", []) or []
    records: List[DecisionRecord] = []
    dose_total = _dose_total_from_rows(rows)
    for row in rows:
        room_raw = row.get("room", "")
        try:
            room = BM.canonicalize_room(room_raw)
        except Exception:
            room = room_raw
        rule_objs: List[Rule] = []
        rule_dicts: List[Dict] = []
        for r in row.get("rules", []) or []:
            metric = r.get("metric", "")
            op = r.get("op", "")
            try:
                threshold = int(r.get("threshold", 0))
            except Exception:
                threshold = 0
            rule_obj = Rule(metric=metric, op=op, threshold=threshold)
            rule_objs.append(rule_obj)
            rule_dicts.append({"type": rule_obj.metric, "op": rule_obj.op, "threshold": rule_obj.threshold})
        for track in ("AM", "PM"):
            entry = row.get(track)
            if not entry:
                continue
            due = entry.get("due", {})
            bp = entry.get("bp")
            tokens_due = CellTokens(
                given=bool(due.get("given", False)),
                time=due.get("time"),
                chart_code=due.get("chart_code"),
                x_mark=bool(due.get("x_mark", False)),
                sbp=due.get("sbp"),
                dbp=due.get("dbp"),
                hr=due.get("hr"),
            )
            tokens_bp = None
            if bp:
                tokens_bp = CellTokens(
                    given=False,
                    time=None,
                    chart_code=None,
                    x_mark=False,
                    sbp=bp.get("sbp"),
                    dbp=bp.get("dbp"),
                    hr=bp.get("hr"),
                )
            source = {
                "page": entry.get("page", 1),
                "col": entry.get("col", 1),
                "rules": rule_dicts,
            }
            decisions = decide_due(
                room=room,
                hall=hall,
                date=date,
                track=track,
                rules=rule_objs,
                tokens_due=tokens_due,
                tokens_bp=tokens_bp,
                source=source,
            )
            records.extend(decisions)
    header_meta = {
        "date_str": date,
        "hall": hall,
        "source": data.get("source") or meta.get("source") or "",
        "pages": meta.get("pages", 1),
    }
    return records, header_meta, dose_total


def run_from_fixture(fixture_path: str) -> Dict:
    data = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    records: List[DecisionRecord]
    header_meta: Dict
    if data.get("records"):
        records = [_decision_from_dict(item) for item in data["records"]]
        header_meta = {
            "date_str": data.get("date_str") or data.get("meta", {}).get("date", ""),
            "hall": data.get("hall") or data.get("meta", {}).get("hall", ""),
            "source": data.get("source") or Path(fixture_path).name,
            "pages": data.get("pages") or data.get("meta", {}).get("pages", 1),
        }
        dose_total = None
    else:
        records, header_meta, dose_total = _records_from_rows(data)
        header_meta.setdefault("source", Path(fixture_path).name)
    if header_meta.get("hall"):
        try:
            header_meta["hall"] = BM.normalize_hall(header_meta["hall"])
        except Exception:
            pass
    payload = build_payload(records, header_meta=header_meta, dose_total=dose_total)
    if not data.get("records"):
        payload["fixture_rows"] = data.get("rows", [])
        payload["fixture_meta"] = data.get("meta", {})
    return payload
