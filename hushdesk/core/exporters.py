"""Export helpers for audit results."""
from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, List, Optional

from .models import DoseResult


class ExportCancelled(RuntimeError):
    """Raised when the caller requests cancellation."""


def _ensure_path(path: Optional[str | Path]) -> Path:
    if path is None or path == "":
        raise ExportCancelled("cancelled")
    return Path(path)


def _exception_entries(doses: Iterable[DoseResult], include_names: bool) -> List[dict]:
    entries: List[dict] = []
    for dose in doses:
        if dose.decision != "EXCEPTION":
            continue
        entry = {
            "room": dose.room,
            "when": dose.time_local.isoformat(),
            "kind": dose.reason,
        }
        if dose.rule:
            entry["op"] = dose.rule.operator
            entry["limit"] = list(dose.rule.limit)
        vital_map = {v.metric: v.value for v in dose.vitals}
        if dose.rule:
            value = vital_map.get(dose.rule.metric)
            if value is not None:
                entry["value"] = value
        if include_names and dose.med_name:
            entry["med_name"] = dose.med_name
        entries.append(entry)
    return entries


def export_json(path: Optional[str | Path], doses: Iterable[DoseResult], meta: dict, include_names: bool = False) -> Path:
    target = _ensure_path(path)
    payload = deepcopy(meta)
    summary = payload.get("summary", {})
    payload["summary"] = summary
    payload.setdefault("meta", {})
    payload["exceptions"] = _exception_entries(doses, include_names)
    if not include_names:
        for entry in payload["exceptions"]:
            entry.pop("med_name", None)
    try:
        target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"Failed to write {target}: {exc}")
    return target


def _format_rule(rule) -> str:
    if not rule:
        return ""
    if rule.operator == "between":
        return f"{rule.metric} between {rule.limit[0]} and {rule.limit[1]}"
    return f"{rule.metric} {rule.operator} {rule.limit[0]}"


def export_txt(path: Optional[str | Path], doses: Iterable[DoseResult], include_names: bool = False) -> Path:
    target = _ensure_path(path)
    lines: List[str] = []
    for dose in doses:
        if dose.decision != "EXCEPTION":
            continue
        parts = [dose.room, "•", dose.time_local.strftime("%H:%M")]
        if include_names and dose.med_name:
            parts.extend(["•", dose.med_name])
        rule_text = _format_rule(dose.rule)
        observed = ""
        if dose.rule:
            vital_map = {v.metric: v.value for v in dose.vitals}
            value = vital_map.get(dose.rule.metric)
            if value is not None:
                observed = f" (observed {value})"
        parts.extend(["•", f"{rule_text}{observed}".strip()])
        lines.append(" ".join(part for part in parts if part))
    try:
        target.write_text("\n".join(lines) or "• No exceptions", encoding="utf-8")
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"Failed to write {target}: {exc}")
    return target
