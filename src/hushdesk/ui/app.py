from __future__ import annotations
import os
import re
import threading
import time
import sys
import importlib
import importlib.resources as pkg_resources
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD  # type: ignore

    DND_OK = True
except Exception:  # pragma: no cover - optional dependency
    DND_FILES = None  # type: ignore[assignment]
    TkinterDnD = None  # type: ignore[assignment]
    DND_OK = False

from hushdesk.ui.theme import load_theme_name, save_theme_name, select_palette
from hushdesk.ui.util import hall_from_rooms
from hushdesk.pdf.backends import MuPdfBackend, PdfUnavailable, PlumberBackend, get_backend
from hushdesk.core.engine import run_sim, run_pdf as pdf_engine
from hushdesk.mar import parser as mar_parser
from hushdesk.pdf.pdfio import extract_text_by_page
from hushdesk.core.pdf.reader import open_pdf, page_text_spans
from hushdesk.core.layout.grid import detect_day_columns, nearest_day_band
from hushdesk.core import building_master as BM
from hushdesk.version import APP_VERSION


def run_simulation(fixture_path: str, room_pattern: str | None = None) -> dict:
    payload = run_sim.run_from_fixture(fixture_path)
    records = payload.get("records", [])
    if room_pattern:
        try:
            regex = re.compile(room_pattern)
        except re.error as exc:  # propagate for UI warning
            raise ValueError(f"Invalid room filter: {exc}") from exc
        filtered_records = [rec for rec in records if regex.search(rec.room)]
        header_meta = dict(payload.get("header", {}))
        header_meta["pages"] = payload.get("pages", 1)
        rows = payload.get("fixture_rows", [])
        filtered_rows = [row for row in rows if regex.search(str(row.get("room", "")))]
        dose_total = 0
        for row in filtered_rows:
            if not row.get("rules"):
                continue
            if "AM" in row:
                dose_total += 1
            if "PM" in row:
                dose_total += 1
        payload = run_sim.build_payload(filtered_records, header_meta=header_meta, dose_total=dose_total or None)
        records = filtered_records
    payload["records"] = records
    payload["rooms"] = sorted({rec.room for rec in records})
    return payload


def _ensure_mmddyyyy(raw: str) -> Optional[str]:
    if not raw:
        return None
    token = str(raw).strip()
    if not token:
        return None
    cleaned = token.replace("_", "-").replace("/", "-")
    candidates = [cleaned, cleaned.replace(" ", "-")]
    for cand in candidates:
        for fmt in ("%m-%d-%Y", "%Y-%m-%d", "%m%d%Y", "%Y%m%d"):
            try:
                dt_obj = datetime.strptime(cand, fmt)
                return dt_obj.strftime("%m-%d-%Y")
            except ValueError:
                continue
    return None


def _infer_date_from_filename(pdf_path: str) -> Optional[str]:
    name = Path(pdf_path).name
    matches = re.findall(r"(\d{4}[-_]\d{2}[-_]\d{2}|\d{2}[-_]\d{2}[-_]\d{4}|\d{8})", name)
    for candidate in matches:
        normalized = _ensure_mmddyyyy(candidate)
        if normalized:
            return normalized
    return None


def _default_date_str() -> str:
    return (datetime.now() - timedelta(days=1)).strftime("%m-%d-%Y")


def _canonical_rooms(rooms: List[str]) -> List[str]:
    canon: List[str] = []
    for room in rooms:
        try:
            canon_room = BM.canonicalize_room(room)
        except Exception:
            continue
        canon.append(canon_room)
    if not canon:
        return []
    # Deduplicate while preserving sorted order for determinism
    return sorted({c for c in canon})


def _parse_day_from_date(date_str: str) -> int:
    parts = date_str.split("-")
    if len(parts) != 3:
        raise ValueError(f"Unrecognized date format: {date_str}")
    try:
        return int(parts[1])
    except ValueError as exc:
        raise ValueError(f"Unrecognized date format: {date_str}") from exc


@dataclass(slots=True)
class DayColumnResolver:
    pdf_path: str
    pages: int
    bands_by_page: Dict[int, Dict[int, tuple[float, float]]]

    @classmethod
    def build(cls, pdf_path: str) -> DayColumnResolver:
        doc = open_pdf(pdf_path)
        try:
            pages = len(doc)
            mapping: Dict[int, Dict[int, tuple[float, float]]] = {}
            for page_index in range(pages):
                spans = page_text_spans(doc, page_index)
                if not spans:
                    continue
                day_spans = _collect_day_spans(spans)
                if not day_spans:
                    continue
                bands = detect_day_columns(doc, page_index)
                if not bands:
                    continue
                assignments: Dict[int, tuple[float, float]] = {}
                for value, center in day_spans:
                    band = nearest_day_band(bands, center)
                    if band is None:
                        continue
                    assignments.setdefault(value, _expand_band(band))
                if assignments:
                    mapping[page_index] = assignments
            return cls(pdf_path=pdf_path, pages=pages, bands_by_page=mapping)
        finally:
            doc.close()

    def bands_for_day(self, day: int) -> Dict[int, tuple[float, float]]:
        matches: Dict[int, tuple[float, float]] = {}
        for page_index, page_map in self.bands_by_page.items():
            band = page_map.get(day)
            if band:
                matches[page_index] = band
        return matches


def _collect_day_spans(spans: List[Dict[str, object]]) -> List[tuple[int, float]]:
    day_spans: List[tuple[int, float]] = []
    for span in spans:
        text = str(span.get("text", "")).strip()
        if not text or not text.isdigit():
            continue
        value = int(text)
        if not (1 <= value <= 31):
            continue
        bbox = span.get("bbox") or (0.0, 0.0, 0.0, 0.0)
        try:
            x0, _, x1, _ = bbox  # type: ignore[misc]
        except Exception:
            continue
        center = (float(x0) + float(x1)) / 2.0
        day_spans.append((value, center))
    return day_spans


def _expand_band(band: tuple[float, float], *, pad_left: float = 6.0, pad_right: float = 24.0) -> tuple[float, float]:
    left, right = band
    return (max(0.0, left - pad_left), right + pad_right)


@dataclass(slots=True)
class HallDetection:
    hall: Optional[str]
    score: int
    candidates: List[str]


def _detect_hall_from_pdf(pdf_path: str) -> HallDetection:
    hall_names = BM.halls()
    if not hall_names:
        return HallDetection(None, 0, [])
    try:
        doc = open_pdf(pdf_path)
    except Exception:
        return HallDetection(None, 0, [])

    try:
        strong_counts = {hall: 0 for hall in hall_names}
        soft_counts = {hall: 0 for hall in hall_names}
        max_pages = min(len(doc), 10)
        for page_index in range(max_pages):
            try:
                page = doc.load_page(page_index)
            except Exception:
                page = None
            spans = page_text_spans(doc, page_index)
            if not spans:
                continue
            header_text: List[str] = []
            footer_text: List[str] = []
            all_text: List[str] = []
            tops: List[float] = []
            bottoms: List[float] = []
            for span in spans:
                text = str(span.get("text", "")).strip()
                if not text:
                    continue
                bbox = span.get("bbox") or (0.0, 0.0, 0.0, 0.0)
                try:
                    top = float(bbox[1])
                    bottom = float(bbox[3])
                except Exception:
                    continue
                tops.append(top)
                bottoms.append(bottom)
                all_text.append(text)
            if not all_text:
                continue
            min_y = min(tops)
            max_y = max(bottoms)
            span_height = max(max_y - min_y, 1.0)
            header_limit = min_y + max(96.0, span_height * 0.18)
            footer_limit = max_y - max(72.0, span_height * 0.12)
            for span in spans:
                text = str(span.get("text", "")).strip()
                if not text:
                    continue
                bbox = span.get("bbox") or (0.0, 0.0, 0.0, 0.0)
                try:
                    top = float(bbox[1])
                    bottom = float(bbox[3])
                except Exception:
                    continue
                if top <= header_limit:
                    header_text.append(text)
                if bottom >= footer_limit:
                    footer_text.append(text)
            joined_header = " ".join(header_text).upper()
            joined_footer = " ".join(footer_text).upper()
            joined_body = " ".join(all_text).upper()
            for hall in hall_names:
                target = hall.upper()
                if target and target in joined_header:
                    strong_counts[hall] += 2
                if target and target in joined_footer:
                    strong_counts[hall] += 1
                if target and target in joined_body:
                    soft_counts[hall] += 1
        best_hall, best_score = max(strong_counts.items(), key=lambda kv: kv[1])
        if best_score <= 1:
            best_hall = None
        candidates = sorted(
            hall_names,
            key=lambda name: (strong_counts.get(name, 0), soft_counts.get(name, 0)),
            reverse=True,
        )
        candidates = [c for c in candidates if strong_counts.get(c, 0) or soft_counts.get(c, 0)][:3]
        return HallDetection(best_hall, best_score, candidates)
    finally:
        doc.close()


def _build_preview_decisions(
    pdf_path: str,
    hall: str,
    date_str: str,
    rooms: List[str],
    day_bands: Dict[int, tuple[float, float]],
    page_count: int,
) -> tuple[List[pdf_engine.DecisionRecord], Dict[str, object]]:
    if not hall:
        raise ValueError("Hall could not be identified.")
    canonical = _canonical_rooms(rooms)
    if not canonical:
        raise ValueError("No recognizable rooms with parametered meds found.")
    if not day_bands:
        raise ValueError("Selected day not present in MAR header.")
    page_indices = sorted(day_bands.keys())
    decisions: List[pdf_engine.DecisionRecord] = []
    for room in canonical:
        recs = pdf_engine.extract_records_for_date(
            pdf_path=pdf_path,
            date_col_index=None,
            date_str_us=date_str,
            hall=hall,
            room=room,
            page_indices=page_indices,
            date_bands=day_bands,
        )
        decisions.extend(recs)
    header_meta = {
        "date_str": date_str,
        "hall": hall,
        "source": Path(pdf_path).name,
        "pages": page_count,
    }
    return decisions, header_meta


def run_pdf_backend(
    pdf_path: str,
    *,
    date_str: str = "",
    room_filter: str | None = None,
    hall_override: str | None = None,
) -> dict:
    try:
        result = mar_parser.parse_mar(pdf_path)
    except Exception as exc:
        return {"ok": False, "error": f"Failed to parse MAR: {exc}"}

    notes: List[str] = []
    meta = dict(result.meta)
    detection = _detect_hall_from_pdf(pdf_path)
    hall_source: Optional[str] = None
    hall_name: Optional[str] = None
    override_value = (hall_override or "").strip()
    if override_value:
        hall_source = "override"
        lowered = override_value.lower()
        hall_name = next((cand for cand in BM.halls() if cand.lower() == lowered), override_value)
    else:
        hall_name = detection.hall or meta.get("hall") or None
        if hall_name:
            hall_source = "detected"
    applied_suggestion = False
    if not hall_name and detection.candidates:
        hall_name = detection.candidates[0]
        hall_source = "suggested"
        applied_suggestion = True
    if hall_name:
        meta["hall"] = hall_name
    hall_detection_payload: Dict[str, object] = {
        "hall": detection.hall,
        "score": detection.score,
        "candidates": detection.candidates,
    }
    if hall_source:
        hall_detection_payload["preview_source"] = hall_source
    if applied_suggestion:
        hall_detection_payload["preview_hall"] = hall_name
        hall_detection_payload["applied_suggestion"] = True
    meta["hall_detection"] = hall_detection_payload
    if hall_source:
        meta["hall_source"] = hall_source
    if not detection.hall:
        notes.append("Unable to confidently infer hall from MAR headers; set hall before exporting.")
        if detection.candidates:
            notes.append(f"Hall suggestions: {', '.join(detection.candidates)}")
    if hall_source == "override":
        notes.append(f"Preview metrics use hall override: {hall_name}.")
    elif hall_source == "suggested":
        notes.append(f"Preview metrics use hall suggestion: {hall_name}. Update if incorrect.")

    normalized_date = _ensure_mmddyyyy(date_str) if date_str else None
    if not normalized_date:
        inferred = _infer_date_from_filename(pdf_path)
        if inferred:
            normalized_date = inferred
            notes.append(f"Date inferred from file name: {normalized_date}")
    if not normalized_date:
        normalized_date = _default_date_str()
        notes.append(f"Date defaulted to yesterday: {normalized_date}")
    meta.setdefault("filters", {})["date"] = normalized_date
    if hall_name:
        meta["filters"]["hall"] = hall_name

    room_regex = None
    if room_filter:
        try:
            room_regex = re.compile(room_filter)
        except re.error as exc:
            notes.append(f"Room filter ignored: {exc}")
        else:
            meta["filters"]["room"] = room_filter

    doses = list(result.records)
    scoped_records = doses
    if hall_name:
        hall_rooms = {BM.canonicalize_room(room) for room in BM.rooms_in_hall(hall_name)}
        scoped: List[Dict[str, object]] = []
        for record in doses:
            room = str(record.get("room", "")).strip()
            try:
                canon = BM.canonicalize_room(room)
            except Exception:
                continue
            if canon in hall_rooms:
                scoped.append(record)
        if scoped:
            scoped_records = scoped
    if room_regex:
        filtered = [rec for rec in scoped_records if room_regex.search(str(rec.get("room", "")))]
        scoped_records = filtered
        if not filtered:
            notes.append("Room filter produced no matching parametered meds.")
    doses = scoped_records

    summary = {
        "reviewed": len(doses),
        "hold_miss": 0,
        "held_ok": 0,
        "compliant": len(doses),
        "dcd": 0,
    }
    sections: Dict[str, List[str]] = {"HOLD-MISS": [], "HELD-APPROPRIATE": [], "COMPLIANT": [], "DC'D": []}
    header_payload: Dict[str, str] = {
        "date_str": normalized_date,
        "hall": hall_name or "",
        "source": Path(pdf_path).name,
    }

    resolver: Optional[DayColumnResolver]
    try:
        resolver = DayColumnResolver.build(pdf_path)
        meta.setdefault("pages", resolver.pages)
    except Exception as exc:
        resolver = None
        notes.append(f"Unable to analyze day columns: {exc}")

    rooms_payload: List[str] = []
    try:
        if hall_name:
            rooms = sorted(BM.rooms_in_hall(hall_name))
            if room_regex:
                rooms = [room for room in rooms if room_regex.search(room)]
            if not rooms:
                raise ValueError("No rooms match the selected hall/filter.")
            day_bands: Dict[int, tuple[float, float]] = {}
            pages_count = resolver.pages if resolver else meta.get("pages", 0)
            if resolver:
                target_day = _parse_day_from_date(normalized_date)
                day_bands = resolver.bands_for_day(target_day)
            decisions, header_meta = _build_preview_decisions(
                pdf_path=pdf_path,
                hall=hall_name,
                date_str=normalized_date,
                rooms=rooms,
                day_bands=day_bands,
                page_count=pages_count if isinstance(pages_count, int) else 0,
            )
            preview_payload = run_sim.build_payload(decisions, header_meta=header_meta)
            preview_records = list(preview_payload.get("records", []))
            if preview_records:
                summary = preview_payload.get("summary", summary)
                sections = preview_payload.get("sections", sections)
                header_payload = preview_payload.get("header", header_meta)
                rooms_payload = list(preview_payload.get("rooms", []))
            else:
                rooms_payload = list(preview_payload.get("rooms", [])) or rooms_payload
                if doses:
                    notes.append(
                        "Preview metrics unavailable: no parametered meds matched the selected hall/day; showing raw parse counts."
                    )
        else:
            notes.append("Select or confirm the hall to enable preview metrics.")
    except ValueError as exc:
        notes.append(str(exc))
    except Exception as exc:
        notes.append(f"Preview summary unavailable: {exc}")
        rooms_payload = []

    return {
        "ok": True,
        "doses": doses,
        "notes": notes,
        "meta": meta,
        "summary": summary,
        "sections": sections,
        "header": header_payload,
        "rooms": rooms_payload,
    }


class HushDeskApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.theme_name = load_theme_name()
        self.palette = select_palette(self.theme_name)
        self.state = {
            "file": None,
            "hall": None,
            "last_payload": None,
            "last_summary": {"reviewed": 0, "hold_miss": 0, "held_ok": 0, "compliant": 0, "dcd": 0},
            "pdf_backend": None,
            "hall_override": None,
            "detected_hall": None,
            "detected_hall_num": None,
            "hall_suggestions": [],
        }
        self._updating_hall_entry = False
        self._suppress_hall_events = False
        self._hall_choices = BM.halls()
        self._fixture_cache: Dict[str, Path] = {}
        self._preflight_status = self._compute_preflight_status()

        self._apply_theme()
        self._build_ui()
        self._show_startup()

    # ------------------------------------------------------------------
    # Theme / UI construction
    def _apply_theme(self) -> None:
        p = self.palette
        self.root.configure(bg=p["bg"])
        style = ttk.Style(self.root)
        style.configure("TLabel", background=p["bg"], foreground=p["text"])
        style.configure("Muted.TLabel", background=p["bg"], foreground=p["muted"])
        style.configure("Card.TFrame", background=p.get("surface", p["bg"]), borderwidth=1, relief="solid")
        style.configure("Banner.TFrame", background=p["banner"]["bg"], borderwidth=1, relief="solid")
        style.configure("Banner.TLabel", background=p["banner"]["bg"], foreground=p["banner"]["text"])
        style.configure("DangerStripe.TFrame", background=p["danger"])
        style.configure("DangerTint.TFrame", background=p["danger_tint"])

    def _build_ui(self) -> None:
        p = self.palette
        self.root.title("HushDesk")
        self.root.geometry("1080x720")

        top = tk.Frame(self.root, bg=p["bg"])
        top.pack(fill="x", pady=(8, 4), padx=12)
        ttk.Label(top, text="HushDesk", font=("Segoe UI", 16, "bold")).pack(side="left")
        top_right = tk.Frame(top, bg=p["bg"])
        top_right.pack(side="right")
        self.theme_btn = ttk.Button(top_right, text=self._theme_button_label(), command=self._toggle_theme)
        self.theme_btn.pack(side="right", padx=(8, 0))
        modules_btn = ttk.Menubutton(top_right, text="••• Modules")
        modules_menu = tk.Menu(modules_btn, tearoff=0)
        modules_menu.add_command(label="BP Meds", state="disabled")
        for label in ("Showers", "Point-of-Care", "Skilled Charting", "MAR/TAR Completion"):
            modules_menu.add_command(label=f"{label}  🔒", state="disabled")
        modules_btn["menu"] = modules_menu
        modules_btn.pack(side="right")

        # Header card ---------------------------------------------------
        self.audit_date_var = tk.StringVar(value="Audit Date: (select MAR)")
        self.hall_var = tk.StringVar(value="Hall not found in header. Type it or pick below.")

        header = ttk.Frame(self.root, style="Card.TFrame")
        header.pack(fill="x", padx=12, pady=(4, 8))
        ttk.Label(header, textvariable=self.audit_date_var, font=("Segoe UI", 18, "bold")).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 2))
        ttk.Label(header, textvariable=self.hall_var, style="Muted.TLabel").grid(row=1, column=0, sticky="w", padx=12)

        hall_edit = tk.Frame(header, bg=p["bg"])
        hall_edit.grid(row=2, column=0, columnspan=2, sticky="w", padx=12, pady=(6, 12))
        ttk.Label(hall_edit, text="Hall override", style="Muted.TLabel").pack(side="left")
        self.hall_entry_var = tk.StringVar()
        self.hall_entry_var.trace_add("write", self._on_hall_entry_changed)
        self.hall_entry = ttk.Entry(hall_edit, textvariable=self.hall_entry_var, width=18)
        self.hall_entry.pack(side="left", padx=(6, 6))
        self.hall_combo = ttk.Combobox(
            hall_edit,
            values=self._hall_choices,
            state="readonly",
            width=18,
        )
        self.hall_combo.bind("<<ComboboxSelected>>", self._on_hall_combo_selected)
        self.hall_combo.pack(side="left")

        file_frame = ttk.Frame(header, style="Card.TFrame")
        file_frame.grid(row=0, column=1, rowspan=3, sticky="ew", padx=12, pady=12)
        header.grid_columnconfigure(1, weight=1)
        ttk.Label(file_frame, text="MAR PDF or Fixture", style="Muted.TLabel").pack(anchor="w", padx=12, pady=(8, 2))
        self.file_var = tk.StringVar(value="Drop a MAR PDF or fixture to get started.")
        file_row = tk.Frame(file_frame, bg=p.get("surface", p["bg"]))
        file_row.pack(fill="x", padx=12, pady=(0, 12))
        self.file_entry = ttk.Entry(file_row, textvariable=self.file_var, width=70)
        self.file_entry.pack(side="left", fill="x", expand=True)
        ttk.Button(file_row, text="Browse...", command=self._on_browse_clicked).pack(side="right", padx=(8, 0))
        if DND_OK and DND_FILES is not None:
            try:
                self.file_entry.drop_target_register(DND_FILES)
                self.file_entry.dnd_bind("<<Drop>>", self._on_drop_files)
            except Exception:
                pass
                pass

        self.banner = ttk.Frame(self.root, style="Banner.TFrame")
        self.banner_msg = ttk.Label(
            self.banner,
            text="Hall not found in header. Type it or pick below.",
            style="Banner.TLabel",
        )
        self.banner_msg.pack(padx=12, pady=6)
        self.banner.pack_forget()

        # Run controls --------------------------------------------------
        run_row = tk.Frame(self.root, bg=p["bg"])
        run_row.pack(fill="x", padx=12, pady=(6, 0))
        primary = ttk.Button(run_row, text="Run Audit", command=self._on_run_audit_clicked)
        primary.pack(side="left")
        self.quick_menu = ttk.Menubutton(run_row, text="Quick Actions")
        qm = tk.Menu(self.quick_menu, tearoff=0)
        qm.add_command(label="Quick Check", command=self._on_quick_check_clicked)
        load_fixture_menu = tk.Menu(qm, tearoff=0)
        load_fixture_menu.add_command(label="Bridgeman (sample)", command=self._load_bridgeman_sample)
        qm.add_cascade(label="Load Fixture", menu=load_fixture_menu)
        self.quick_menu["menu"] = qm
        self._quick_actions_menu = qm
        self.quick_menu.pack(side="left", padx=(8, 0))

        filter_box = tk.Frame(run_row, bg=p["bg"])
        filter_box.pack(side="right")
        ttk.Label(filter_box, text="Filter rooms", style="Muted.TLabel").pack(side="left", padx=(0, 6))
        self.filter_var = tk.StringVar()
        ttk.Entry(filter_box, textvariable=self.filter_var, width=18).pack(side="left")
        for chip in ("100", "200", "300", "400"):
            btn = ttk.Button(filter_box, text=chip, command=lambda c=chip: self.filter_var.set(fr"^{c[0]}\d\d-"))
            btn.pack(side="left", padx=3)

        # Progress + Summary -------------------------------------------
        progress_card = ttk.Frame(self.root, style="Card.TFrame")
        progress_card.pack(fill="x", padx=12, pady=(12, 6))
        self.progress = ttk.Progressbar(progress_card, mode="determinate", maximum=100)
        self.progress.pack(fill="x", padx=12, pady=(10, 6))
        self.progress_lbl = ttk.Label(progress_card, text="", style="Muted.TLabel")
        self.progress_lbl.pack(anchor="w", padx=12, pady=(0, 10))

        sum_row = tk.Frame(self.root, bg=p["bg"])
        sum_row.pack(fill="x", padx=12, pady=(0, 8))
        self.sum_lbls = {
            "reviewed": ttk.Label(sum_row, text="Reviewed (parametered doses touched) 0"),
            "hold_miss": ttk.Label(sum_row, text="Hold-Miss 0"),
            "held_ok": ttk.Label(sum_row, text="Held-Appropriate 0"),
            "compliant": ttk.Label(sum_row, text="Compliant (accurate BP rules) 0"),
            "dcd": ttk.Label(sum_row, text="DC'D 0"),
        }
        self.sum_lbls["reviewed"].pack(side="left")
        ttk.Label(sum_row, text="  |  ", style="Muted.TLabel").pack(side="left")
        self.sum_lbls["hold_miss"].pack(side="left")
        ttk.Label(sum_row, text="  |  ", style="Muted.TLabel").pack(side="left")
        self.sum_lbls["held_ok"].pack(side="left")
        ttk.Label(sum_row, text="  |  ", style="Muted.TLabel").pack(side="left")
        self.sum_lbls["compliant"].pack(side="left")
        ttk.Label(sum_row, text="  |  ", style="Muted.TLabel").pack(side="left")
        self.sum_lbls["dcd"].pack(side="left")

        # Results container --------------------------------------------
        self.results = tk.Frame(self.root, bg=p["bg"])
        self.results.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        # Actions -------------------------------------------------------
        actions = tk.Frame(self.root, bg=p["bg"])
        actions.pack(fill="x", padx=12, pady=(0, 8))
        ttk.Button(actions, text="Copy Checklist", command=self._copy_txt).pack(side="left")
        ttk.Button(actions, text="Save TXT", command=self._save_txt).pack(side="left", padx=(8, 0))

        # Footer --------------------------------------------------------
        footer = tk.Frame(self.root, bg=p["bg"])
        footer.pack(fill="x", padx=12, pady=(4, 8))

        info_row = tk.Frame(footer, bg=p["bg"])
        info_row.pack(fill="x")
        self.footer_info_var = tk.StringVar(value=self._footer_info_text())
        ttk.Label(info_row, textvariable=self.footer_info_var, style="Muted.TLabel").pack(side="left")
        ttk.Button(info_row, text="Safety info", command=self._show_safety).pack(side="right")

        status_row = tk.Frame(footer, bg=p["bg"])
        status_row.pack(fill="x", pady=(2, 0))
        self.preflight_var = tk.StringVar(value=self._format_preflight_status())
        ttk.Label(status_row, textvariable=self.preflight_var, style="Muted.TLabel").pack(side="left")
        self.footer_time = ttk.Label(status_row, text="Time: -", style="Muted.TLabel")
        self.footer_time.pack(side="right")

        self._set_summary(self.state["last_summary"])

    # ------------------------------------------------------------------
    # Theme toggle helpers
    def _theme_button_label(self) -> str:
        return "Dark" if self.theme_name != "dark" else "Light"

    def _toggle_theme(self) -> None:
        self.theme_name = "dark" if self.theme_name != "dark" else "light"
        save_theme_name(self.theme_name)
        self.palette = select_palette(self.theme_name)
        self._apply_theme()
        self._repaint()
        self.theme_btn.config(text=self._theme_button_label())
        self._set_summary(self.state["last_summary"])

    def _repaint(self) -> None:
        bg = self.palette["bg"]
        for widget in self.root.winfo_children():
            try:
                widget.configure(bg=bg)
            except tk.TclError:
                pass

    # ------------------------------------------------------------------
    # Startup + dialogs
    def _show_startup(self) -> None:
        top = tk.Toplevel(self.root)
        top.title("Welcome to HushDesk")
        top.transient(self.root)
        top.grab_set()
        p = self.palette
        top.configure(bg=p["bg"])
        frame = tk.Frame(top, bg=p["bg"])
        frame.pack(padx=20, pady=18)

        def add_section(title: str, body: str) -> None:
            tk.Label(frame, text=title, font=("Segoe UI", 12, "bold"), bg=p["bg"], fg=p["text"]).pack(anchor="w")
            tk.Label(frame, text=body, justify="left", wraplength=520, bg=p["bg"], fg=p["text"]).pack(anchor="w", pady=(0, 10))

        add_section("What HushDesk does", "Checks BP med pass compliance by matching hold rules to what was documented for each dose on the chosen date.")
        add_section("What you'll see", "• Hold-Miss - should've been held, but was given.\n• Held-Appropriate - valid hold code (4, 6, 11, 12, 15).\n• Compliant - accurately follows the BP hold rules.\n• DC'D - clearly X'd out for the day.\n• Reviewed - every parametered dose we touched.")
        add_section("Privacy", "• Runs completely offline. HushDesk never uses the internet.\n• Never stores PHI/PII (outputs are hall + room only).\n• Files you save remain on your machine with private permissions.\n• Encryption at rest is planned.")
        ttk.Button(frame, text="Got it", command=top.destroy).pack(anchor="e", pady=(4, 0))

    def _show_safety(self) -> None:
        messagebox.showinfo(
            "Safety",
            "• Runs completely offline (no internet).\n"
            "• Never stores PHI/PII (hall + room only).\n"
            "• Files you save stay on your machine with private permissions.\n"
            "• Encryption at rest is planned.",
        )

    def _show_pdf_missing_dialog(self) -> None:
        body = (
            "This build doesn't have the PDF reader bundled.\n\n"
            "Try now: Load a sample Fixture (no PHI) from Quick Actions to see HushDesk work.\n"
            "Next build: include the PDF reader so real MARs open normally."
        )
        prompt = "Open Quick Actions now?\n\n" + body
        if messagebox.askyesno("Can't read this MAR yet", prompt):
            try:
                self._open_quick_actions_menu_highlight("Load Fixture")
            except Exception:
                self._load_fixture_and_run("bridgeman_sample.json")

    def _open_quick_actions_menu(self) -> None:
        menu = getattr(self, "_quick_actions_menu", None)
        btn = getattr(self, "quick_menu", None)
        if not menu or not btn:
            return
        try:
            x = btn.winfo_rootx()
            y = btn.winfo_rooty() + btn.winfo_height()
            menu.tk_popup(x, y)
        except Exception:
            pass
        finally:
            try:
                menu.grab_release()
            except Exception:
                pass

    def _open_quick_actions_menu_highlight(self, label: str) -> None:
        menu = getattr(self, "_quick_actions_menu", None)
        btn = getattr(self, "quick_menu", None)
        if not menu or not btn:
            raise RuntimeError("Quick Actions menu unavailable.")
        self._open_quick_actions_menu()
        try:
            index = menu.index(label)
        except tk.TclError:
            index = None
        if index is not None:
            try:
                menu.activate(index)
            except tk.TclError:
                pass

    def _load_fixture_and_run(self, filename: str) -> None:
        path = self._resolve_fixture(filename)
        if not path:
            messagebox.showerror("HushDesk", f"Fixture '{filename}' is not bundled in this build.")
            return
        self._on_file_chosen(str(path))

    def _resolve_fixture(self, filename: str) -> Optional[Path]:
        cached = self._fixture_cache.get(filename)
        if cached and cached.exists():
            return cached
        base_meipass = getattr(sys, "_MEIPASS", None)
        if base_meipass:
            candidate = Path(base_meipass) / "fixtures" / filename
            if candidate.exists():
                self._fixture_cache[filename] = candidate
                return candidate
        try:
            with pkg_resources.as_file(pkg_resources.files("hushdesk").joinpath("fixtures", filename)) as res_path:
                if res_path.exists():
                    self._fixture_cache[filename] = res_path
                    return res_path
        except Exception:
            pass
        project_root = Path(__file__).resolve().parents[3]
        repo_candidate = project_root / "fixtures" / filename
        if repo_candidate.exists():
            self._fixture_cache[filename] = repo_candidate
            return repo_candidate
        package_candidate = Path(__file__).resolve().parents[1] / "fixtures" / filename
        if package_candidate.exists():
            self._fixture_cache[filename] = package_candidate
            return package_candidate
        return None

    def _load_bridgeman_sample(self) -> bool:
        path = self._resolve_fixture("bridgeman_sample.json")
        if not path:
            messagebox.showerror("HushDesk", "Sample fixture not bundled in this build.")
            return False
        self._on_file_chosen(str(path))
        return True

    # ------------------------------------------------------------------
    # File selection
    def _normalize_path(self, raw_path: str) -> str:
        candidate = (raw_path or "").strip()
        if candidate.startswith("{") and candidate.endswith("}"):
            candidate = candidate[1:-1]
        return candidate.strip().strip('"')

    def _toast(self, message: str) -> None:
        messagebox.showwarning("HushDesk", message)

    def _on_drop_files(self, event) -> None:  # type: ignore[override]
        data = getattr(event, "data", "")
        try:
            paths = self.root.tk.splitlist(data)
        except Exception:
            paths = []
        if not paths:
            return
        candidate = self._normalize_path(paths[0])
        if not candidate:
            return
        if os.path.isdir(candidate):
            self._toast("Drop a file, not a folder.")
            return
        self._on_file_chosen(candidate)

    def _on_browse_clicked(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("MAR PDF/Fixture", "*.pdf *.json")])
        if path:
            self._on_file_chosen(path)

    def _on_file_chosen(self, raw_path: str) -> None:
        normalized = self._normalize_path(raw_path)
        if not normalized:
            return
        self.file_var.set(normalized)
        if self._quick_check_for_path(normalized):
            self._start_quick_check()

    def _quick_check_for_path(self, path_text: str) -> bool:
        normalized = self._normalize_path(path_text)
        if not normalized:
            return False
        path = Path(normalized)
        if path.is_dir():
            self._toast("Drop a file, not a folder.")
            return False
        if not path.exists():
            self._toast("That file could not be found.")
            return False
        suffix = path.suffix.lower()
        if suffix not in {".pdf", ".json"}:
            self._toast("Unsupported file type. Use a MAR PDF or Fixture JSON.")
            return False
        if suffix == ".pdf":
            try:
                backend = get_backend()
            except PdfUnavailable:
                self._show_pdf_missing_dialog()
                return False
            if isinstance(backend, MuPdfBackend):
                self.state["pdf_backend"] = "mupdf"
                self._preflight_status["mupdf"] = True
            elif isinstance(backend, PlumberBackend):
                self.state["pdf_backend"] = "pdfplumber"
                self._preflight_status["pdfplumber"] = True
            else:
                self.state["pdf_backend"] = backend.__class__.__name__.lower()
        else:
            self.state["pdf_backend"] = "fixture"
        self._set_file(path)
        if hasattr(self, "preflight_var"):
            self.preflight_var.set(self._format_preflight_status())
        return True

    def _on_quick_check_clicked(self) -> None:
        path = (self.file_var.get() or "").strip()
        if not path:
            self._toast("Pick a MAR PDF or Fixture first.")
            return
        if self._quick_check_for_path(path):
            self._start_quick_check()

    def _on_run_audit_clicked(self) -> None:
        path = (self.file_var.get() or "").strip()
        if not path:
            self._toast("Pick a MAR PDF or Fixture first.")
            return
        if self._quick_check_for_path(path):
            self._start_audit()

    def _set_file(self, path: Path) -> None:
        self.state["file"] = path
        self.file_var.set(str(path))
        rooms: List[str] = []
        date_display: Optional[str] = None
        if path.suffix.lower() == ".json":
            try:
                fx = run_sim.load_fixture(str(path))
                rooms = [row.get("room") for row in fx.get("rows", []) if row.get("room")]
                date_display = fx["meta"].get("date")
            except Exception:
                rooms = []
        hall, hall_num = hall_from_rooms(rooms)
        self._refresh_hall_status(hall, hall_num)
        if date_display:
            self.audit_date_var.set(f"Audit Date: {date_display} (Central)")
        else:
            self.audit_date_var.set("Audit Date: (select date)")

    def _set_hall_entry_text(self, value: str) -> None:
        self._suppress_hall_events = True
        try:
            self.hall_entry_var.set(value or "")
        finally:
            self._suppress_hall_events = False

    def _set_hall_combo_value(self, value: str) -> None:
        self._suppress_hall_events = True
        try:
            if value and value in self._hall_choices:
                self.hall_combo.set(value)
            elif not value:
                self.hall_combo.set("")
        finally:
            self._suppress_hall_events = False

    def _on_hall_entry_changed(self, *_args) -> None:
        if self._suppress_hall_events:
            return
        value = self.hall_entry_var.get().strip()
        self.state["hall_override"] = value or None
        self._refresh_hall_status(self.state.get("detected_hall"), self.state.get("detected_hall_num"))
        self._update_cached_payload_hall()

    def _on_hall_combo_selected(self, _event) -> None:
        value = self.hall_combo.get().strip()
        self._set_hall_entry_text(value)
        if not self._suppress_hall_events:
            self.state["hall_override"] = value or None
            self._refresh_hall_status(self.state.get("detected_hall"), self.state.get("detected_hall_num"))
            self._update_cached_payload_hall()

    def _refresh_hall_status(self, detected_hall: Optional[str], detected_hall_num: Optional[int | str]) -> None:
        self.state["detected_hall"] = detected_hall
        self.state["detected_hall_num"] = detected_hall_num
        override = (self.state.get("hall_override") or "").strip()
        suggestions = list(self.state.get("hall_suggestions") or [])
        hall_source = self.state.get("hall_source")
        if override:
            suffix = " (override)" if hall_source == "override" else " (chosen)"
            self.hall_var.set(f"Hall: {override}{suffix}")
            self._set_hall_entry_text(override)
            self._set_hall_combo_value(override)
            self.banner.pack_forget()
        elif detected_hall and detected_hall_num:
            suffix = " (suggested)" if hall_source == "suggested" else " (auto)"
            self.hall_var.set(f"Hall: {detected_hall_num}{suffix}")
            self._set_hall_entry_text(detected_hall)
            self._set_hall_combo_value(detected_hall)
            self.banner.pack_forget()
        else:
            message = "Hall not found in header. Type it or pick below."
            if suggestions:
                suggestion_text = ", ".join(suggestions[:3])
                message = f"Hall not found in header. Suggestions: {suggestion_text}. Type it or pick below."
                if hall_source == "suggested":
                    message = f"Using hall suggestion {suggestions[0]} for preview. Confirm or adjust below."
            self.hall_var.set(message)
            self.banner_msg.configure(text=message)
            self.banner.pack(fill="x", padx=12, pady=(0, 8))
            if not override:
                self._set_hall_entry_text("")
                self._set_hall_combo_value("")
                if suggestions:
                    self._set_hall_combo_value(suggestions[0])
        current = override or detected_hall or ""
        self.state["hall"] = current or None
        self._update_cached_payload_hall()

    def _probe_module(self, module: str) -> bool:
        try:
            importlib.import_module(module)
            return True
        except Exception:
            return False

    def _compute_preflight_status(self) -> Dict[str, bool]:
        return {
            "mupdf": self._probe_module("fitz"),
            "pdfplumber": self._probe_module("pdfplumber"),
            "dnd": bool(DND_OK),
        }

    def _format_preflight_status(self) -> str:
        status = self._preflight_status
        check = lambda ok: "✓" if ok else "✗"
        return (
            f"PDF: MuPDF {check(status.get('mupdf', False))} | "
            f"Fallback {check(status.get('pdfplumber', False))} | "
            f"DnD {check(status.get('dnd', False))} | Safety: On"
        )

    def _footer_info_text(self) -> str:
        return f"v{APP_VERSION} • America/Chicago • Safety: On."

    def _ensure_pdf_backend(self, path: Path):
        backend = get_backend()
        try:
            doc = backend.open(str(path))
        except Exception as exc:
            raise RuntimeError("HushDesk couldn't open that MAR PDF.") from exc
        close = getattr(doc, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass
        return backend

    def _run_pdf_pipeline(
        self, path: Path, backend: Any, room_pattern: str | None, hall_override: str | None
    ) -> dict:
        if isinstance(backend, MuPdfBackend):
            backend_name = "mupdf"
            self._preflight_status["mupdf"] = True
        elif isinstance(backend, PlumberBackend):
            backend_name = "pdfplumber"
            self._preflight_status["pdfplumber"] = True
        else:
            backend_name = backend.__class__.__name__.lower()
        self.state["pdf_backend"] = backend_name
        if hasattr(self, "preflight_var"):
            self.preflight_var.set(self._format_preflight_status())
        return run_pdf_backend(str(path), date_str="", room_filter=room_pattern, hall_override=hall_override)

    # ------------------------------------------------------------------
    # Rendering helpers
    def _set_summary(self, summary: Dict[str, int]) -> None:
        self.state["last_summary"] = summary
        nums = self.palette["summary_nums"]
        self.sum_lbls["reviewed"].configure(
            text=f"Reviewed (parametered doses touched) {int(summary.get('reviewed', 0))}", foreground=nums["reviewed"]
        )
        self.sum_lbls["hold_miss"].configure(
            text=f"Hold-Miss {int(summary.get('hold_miss', 0))}", foreground=nums["hold_miss"]
        )
        self.sum_lbls["held_ok"].configure(
            text=f"Held-Appropriate {int(summary.get('held_ok', 0))}", foreground=nums["held_ok"]
        )
        self.sum_lbls["compliant"].configure(
            text=f"Compliant (accurate BP rules) {int(summary.get('compliant', 0))}", foreground=nums["compliant"]
        )
        self.sum_lbls["dcd"].configure(
            text=f"DC'D {int(summary.get('dcd', 0))}", foreground=nums["dcd"]
        )

    def _clear_results(self) -> None:
        for widget in self.results.winfo_children():
            widget.destroy()

    def _render_violations(self, violations: List[str]) -> None:
        if not violations:
            ttk.Label(self.results, text="No exceptions.", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(2, 4))
            return
        ttk.Label(self.results, text="Violations", font=("Segoe UI", 11, "bold"), foreground=self.palette["danger"]).pack(anchor="w", pady=(2, 4))
        for line in violations:
            row = tk.Frame(self.results, bg=self.palette["bg"])
            tk.Frame(row, width=3, height=20, bg=self.palette["danger"]).pack(side="left", fill="y")
            tint = tk.Frame(row, bg=self.palette["danger_tint"])
            tint.pack(side="left", fill="x", expand=True)
            tk.Label(tint, text=line, bg=self.palette["danger_tint"], fg=self.palette["text"]).pack(anchor="w", padx=8, pady=2)
            row.pack(fill="x", pady=2)

    def _render_all_reviewed(self, groups: Dict[str, List[str]]) -> None:
        card = ttk.Frame(self.results, style="Card.TFrame")
        card.pack(fill="both", expand=True, pady=(8, 0))
        header = tk.Frame(card, bg=self.palette.get("surface", self.palette["bg"]))
        header.pack(fill="x")
        ttk.Label(header, text="All Reviewed", font=("Segoe UI", 11, "bold")).pack(side="left", padx=12, pady=8)
        body = tk.Frame(card, bg=self.palette.get("surface", self.palette["bg"]))
        expanded = {"v": False}

        def populate() -> None:
            for child in body.winfo_children():
                child.destroy()
            mapping = [
                ("HOLD-MISS", "HOLD-MISS"),
                ("HELD-APPROPRIATE", "HELD-Appropriate"),
                ("COMPLIANT", "COMPLIANT"),
                ("DC'D", "DC'D"),
            ]
            for key, title in mapping:
                items = groups.get(key, [])
                section = tk.Frame(body, bg=self.palette.get("surface", self.palette["bg"]))
                section.pack(fill="x", padx=12, pady=(6, 2))
                ttk.Label(section, text=f"{title} ({len(items)})", style="Muted.TLabel").pack(anchor="w")
                for line in items:
                    if key == "HOLD-MISS":
                        row = tk.Frame(section, bg=self.palette.get("surface", self.palette["bg"]))
                        row.pack(fill="x", pady=1)
                        tk.Frame(row, bg=self.palette["danger"], width=3, height=20).pack(side="left", fill="y")
                        tk.Label(row, text=line, bg=self.palette["danger_tint"], fg=self.palette["text"]).pack(side="left", fill="x", expand=True, padx=8, pady=2)
                    else:
                        tk.Label(section, text=line, bg=self.palette.get("surface", self.palette["bg"]), fg=self.palette["text"]).pack(anchor="w", padx=8, pady=2)

        def toggle() -> None:
            expanded["v"] = not expanded["v"]
            if expanded["v"]:
                populate()
                body.pack(fill="both", expand=True)
                toggle_btn.configure(text="Hide")
            else:
                body.pack_forget()
                toggle_btn.configure(text="Show")

        toggle_btn = ttk.Button(header, text="Show", command=toggle)
        toggle_btn.pack(side="right", padx=12)



    def _render_pdf_preview(self, payload: dict) -> None:
        notes = payload.get("notes", [])
        if not payload.get("doses"):
            ttk.Label(
                self.results,
                text="Couldn't find the MAR schedule grid on this PDF. Check the month header and Chart Codes legend are present.",
                font=("Segoe UI", 11, "bold"),
                foreground=self.palette["danger"],
                wraplength=720,
                justify="left",
            ).pack(anchor="w", padx=12, pady=(12, 4))
            for note in notes:
                ttk.Label(self.results, text=f"Note: {note}", style="Muted.TLabel", wraplength=720, justify="left").pack(
                    anchor="w", padx=16, pady=2
                )
            return

        card = ttk.Frame(self.results, style="Card.TFrame")
        card.pack(fill="both", expand=True, pady=(8, 0))
        surface = self.palette.get("surface", self.palette["bg"])
        header_frame = tk.Frame(card, bg=surface)
        header_frame.pack(fill="x")
        ttk.Label(header_frame, text="MAR Quick Review", font=("Segoe UI", 11, "bold")).pack(side="left", padx=12, pady=8)

        body = tk.Frame(card, bg=surface)
        body.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        text = tk.Text(
            body,
            wrap="word",
            font=("Segoe UI", 10),
            bg=surface,
            fg=self.palette["text"],
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            exportselection=True,
            cursor="arrow",
        )
        text.configure(insertbackground=self.palette["text"])
        text.pack(fill="both", expand=True)
        text.tag_configure("bold", font=("Segoe UI", 10, "bold"))
        text.tag_configure("section", font=("Segoe UI", 10, "bold"), foreground=self.palette["danger"])
        text.tag_configure("muted", foreground=self.palette.get("muted", "#6c757d"))

        header = payload.get("header", {})
        meta_info = payload.get("meta", {})
        date_display = header.get("date_str") or "--"
        hall_display = header.get("hall") or "--"
        hall_source = meta_info.get("hall_source")
        if hall_display != "--" and hall_source:
            if hall_source == "suggested":
                hall_display = f"{hall_display} (suggested)"
            elif hall_source == "override":
                hall_display = f"{hall_display} (override)"
            elif hall_source == "detected":
                hall_display = f"{hall_display} (auto)"
        meta_source = meta_info.get("source")
        source_display = header.get("source") or meta_source or "MAR.pdf"
        text.insert("end", f"Date: {date_display}\n", ("bold",))
        text.insert("end", f"Hall: {hall_display}\n", ("bold",))
        text.insert("end", f"Source: {source_display}\n\n")

        summary = payload.get("summary", {})
        summary_lines = [
            f"Reviewed: {int(summary.get('reviewed', 0))}",
            f"Hold-Miss: {int(summary.get('hold_miss', 0))}",
            f"Held-Appropriate: {int(summary.get('held_ok', 0))}",
            f"Compliant (accurate BP rules): {int(summary.get('compliant', 0))}",
            f"DC'D: {int(summary.get('dcd', 0))}",
        ]
        text.insert("end", "\n".join(summary_lines) + "\n\n")

        sections = payload.get("sections", {})
        hold_miss_items = list(sections.get("HOLD-MISS", []))
        text.insert("end", "HOLD-MISS\n", ("section",))
        if hold_miss_items:
            for line in hold_miss_items:
                formatted = line.replace(" - ", " \u2014 ", 1)
                text.insert("end", f"  {formatted}\n")
        else:
            text.insert("end", "  -- none --\n", ("muted",))

        reviewed_total = summary.get("reviewed")
        if reviewed_total is None:
            reviewed_total = len(payload.get("doses", []))
        text.insert(
            "end",
            f"\nParsed doses: {int(reviewed_total)} | Pages scanned: {meta_info.get('pages', '?')}\n",
            ("muted",),
        )

        guidance_text = (
            "Run the full audit to export the checklist and drill into each hold reason."
            if hold_miss_items
            else "Run the full audit to export the checklist and confirm chart codes."
        )
        text.insert("end", f"{guidance_text}\n", ("muted",))

        for note in notes:
            text.insert("end", f"\nNote: {note}\n", ("muted",))

        allowed_nav = {
            "Left",
            "Right",
            "Up",
            "Down",
            "Home",
            "End",
            "Prior",
            "Next",
        }

        def _block_edit(event: tk.Event) -> str | None:
            control = bool(event.state & 0x0004)
            if control and event.keysym.lower() in {"c", "a"}:
                return None
            if event.keysym in allowed_nav:
                return None
            if event.keysym in {"Shift_L", "Shift_R", "Control_L", "Control_R"}:
                return None
            return "break"

        text.bind("<KeyPress>", _block_edit)
        text.bind("<<Paste>>", lambda e: "break")
        text.bind("<<Cut>>", lambda e: "break")
        text.bind("<Delete>", lambda e: "break")
        text.bind("<BackSpace>", lambda e: "break")

    def _apply_hall_detection(self, payload: dict, fallback: tuple[Optional[str], Optional[int]] | None = None) -> None:
        meta = payload.get("meta") or {}
        detection = meta.get("hall_detection") or {}
        suggestions = list(detection.get("candidates") or [])
        self.state["hall_suggestions"] = suggestions
        self.state["hall_source"] = detection.get("preview_source") or meta.get("hall_source")
        detected = detection.get("hall")
        hall_num: Optional[int | str] = None
        if fallback is None:
            header_hall = (payload.get("header") or {}).get("hall") or None
            if header_hall:
                try:
                    rooms = list(BM.rooms_in_hall(header_hall))
                except Exception:
                    rooms = []
                if rooms:
                    hall_guess, hall_guess_num = hall_from_rooms(rooms[:4] or rooms)
                    fallback = (hall_guess or header_hall, hall_guess_num)
                else:
                    fallback = (header_hall, None)
        if detected:
            try:
                rooms = list(BM.rooms_in_hall(detected))
                hall_guess, hall_guess_num = hall_from_rooms(rooms[:4] or rooms)
                detected = hall_guess or detected
                hall_num = hall_guess_num
            except Exception:
                hall_num = None
        elif fallback:
            detected, hall_num = fallback
        else:
            detected = self.state.get("detected_hall")
            hall_num = self.state.get("detected_hall_num")
        self._refresh_hall_status(detected, hall_num)

    def _render_pdf_error(self, message: str) -> None:
        self._clear_results()
        ttk.Label(
            self.results,
            text=message,
            font=("Segoe UI", 11, "bold"),
            foreground=self.palette["danger"],
            wraplength=720,
            justify="left",
        ).pack(anchor="w", padx=12, pady=(12, 4))

    def _handle_pdf_preview_result(self, payload: dict, elapsed: float) -> None:
        self._apply_hall_detection(payload)
        error_message = ""
        if not payload.get("ok", False):
            error_message = payload.get("error", "Failed to parse MAR.")
            if "no schedule grid found" in error_message.lower():
                error_message = (
                    "Couldn't find the MAR schedule grid on this PDF. Check the month header and Chart Codes legend are present."
                )
            self._render_pdf_error(error_message)
            self._set_summary({"reviewed": 0, "hold_miss": 0, "held_ok": 0, "compliant": 0, "dcd": 0})
            self.footer_time.configure(text=f"Time: {elapsed:.1f}s")
            return

        summary = payload.get("summary")
        if not summary:
            doses = payload.get("doses", [])
            summary = {
                "reviewed": len(doses),
                "hold_miss": 0,
                "held_ok": 0,
                "compliant": len(doses),
                "dcd": 0,
            }
        self._set_summary(summary)
        self._clear_results()
        self._render_pdf_preview(payload)
        self.footer_time.configure(text=f"Time: {elapsed:.1f}s")

    # ------------------------------------------------------------------
    # Backend interaction helpers
    def _selected_path(self) -> Path | None:
        return self.state["file"]

    def _compute_payload(self) -> dict:
        path = self._selected_path()
        if not path:
            raise RuntimeError("Select a MAR (PDF or fixture) first.")
        room_pattern = self.filter_var.get().strip() or None
        suffix = path.suffix.lower()
        if suffix == ".json":
            payload = run_simulation(str(path), room_pattern)
        elif suffix == ".pdf":
            backend = self._ensure_pdf_backend(path)
            hall_override = (self.state.get("hall_override") or "").strip() or None
            payload = self._run_pdf_pipeline(path, backend, room_pattern, hall_override)
        else:
            raise RuntimeError("Unsupported file type. Use a MAR PDF or fixture JSON.")
        self._apply_hall_override_to_payload(payload)
        return payload

    def _current_hall_value(self) -> str:
        override = (self.state.get("hall_override") or "").strip()
        if override:
            return override
        detected = self.state.get("detected_hall")
        return (detected or "").strip()

    def _update_cached_payload_hall(self) -> None:
        payload = self.state.get("last_payload")
        if not payload or "header" not in payload:
            return
        hall_value = self._current_hall_value()
        header = payload.setdefault("header", {})
        if hall_value:
            header["hall"] = hall_value
        else:
            header.pop("hall", None)

    def _apply_hall_override_to_payload(self, payload: dict) -> None:
        if "header" not in payload:
            return
        header = payload.setdefault("header", {})
        hall_value = (self.state.get("hall_override") or "").strip()
        if not hall_value:
            hall_value = (header.get("hall") or self.state.get("detected_hall") or "").strip()
        if hall_value:
            header["hall"] = hall_value
            self.state["hall"] = hall_value
        else:
            header.pop("hall", None)
        self._update_cached_payload_hall()

    def _update_header_from_payload(self, payload: dict) -> None:
        if "header" not in payload:
            return
        rooms = payload.get("rooms", [])
        fallback: tuple[Optional[str], Optional[int]] | None = None
        if rooms:
            try:
                hall_guess, hall_num = hall_from_rooms(rooms)
                if hall_guess:
                    fallback = (hall_guess, hall_num)
            except Exception:
                fallback = None
        header_hall = (payload.get("header") or {}).get("hall")
        if header_hall:
            fallback = (header_hall, fallback[1] if fallback else None)
        self._apply_hall_detection(payload, fallback=fallback)
        self.audit_date_var.set(f"Audit Date: {payload['header']['date_str']} (Central)")

    def _after_start(self, text: str, mode: str) -> None:
        if mode == "quick":
            self.progress.configure(mode="indeterminate")
            self.progress.start(55)
            self.progress_lbl.configure(text=text)
        else:
            self.progress.configure(mode="determinate", value=0, maximum=100)
            self.progress_lbl.configure(text=text)

    def _after_finish(self) -> None:
        self.progress.stop()
        self.progress_lbl.configure(text="")
        self.progress.configure(value=0)

    def _start_quick_check(self) -> None:
        try:
            self._compute_payload  # ensure file selected check earlier
        except RuntimeError:
            pass
        if not self._selected_path():
            messagebox.showwarning("HushDesk", "Select a MAR (PDF or fixture) first.")
            return
        self._clear_results()
        self._after_start("Checking...", mode="quick")

        def worker():
            start = time.time()
            try:
                payload = self._compute_payload()
            except PdfUnavailable:
                self.state["pdf_backend"] = None
                self.root.after(0, self._show_pdf_missing_dialog)
            except Exception as exc:  # relay to UI
                self.root.after(0, lambda: messagebox.showerror("HushDesk", f"Quick Check failed:\n{exc}"))
            else:
                elapsed = time.time() - start
                self.root.after(0, lambda: self._on_quick_check_done(payload, elapsed))
            finally:
                self.root.after(0, self._after_finish)

        threading.Thread(target=worker, daemon=True).start()

    def _on_quick_check_done(self, payload: dict, elapsed: float) -> None:
        self.state["last_payload"] = payload
        if "ok" in payload:
            self._handle_pdf_preview_result(payload, elapsed)
            return
        self._update_header_from_payload(payload)
        self._set_summary(payload["summary"])
        self._clear_results()
        self._render_violations(payload.get("violations", []))
        self.footer_time.configure(text=f"Time: {elapsed:.1f}s")

    def _start_audit(self) -> None:
        if not self._selected_path():
            messagebox.showwarning("HushDesk", "Select a MAR (PDF or fixture) first.")
            return
        self._clear_results()
        self._after_start("Preparing...", mode="audit")

        def worker():
            start = time.time()
            try:
                payload = self._compute_payload()
            except PdfUnavailable:
                self.state["pdf_backend"] = None
                self.root.after(0, self._show_pdf_missing_dialog)
                self.root.after(0, self._after_finish)
                return
            except Exception as exc:
                self.root.after(0, lambda: messagebox.showerror("HushDesk", f"Run Audit failed:\n{exc}"))
                self.root.after(0, self._after_finish)
                return
            elapsed = time.time() - start
            self.root.after(0, lambda: self._on_run_audit_done(payload, elapsed))

        threading.Thread(target=worker, daemon=True).start()

    def _animate_pages(self, pages: int, callback) -> None:
        pages = max(pages, 1)

        def step(i: int) -> None:
            self.progress["value"] = (i / pages) * 100
            self.progress_lbl.configure(text=f"Page {i} of {pages}")
            if i < pages:
                self.root.after(60, lambda: step(i + 1))
            else:
                callback()

        step(1)

    def _on_run_audit_done(self, payload: dict, elapsed: float) -> None:
        self.state["last_payload"] = payload
        if "ok" in payload:
            self._handle_pdf_preview_result(payload, elapsed)
            self._after_finish()
            return
        self._update_header_from_payload(payload)
        self._set_summary(payload["summary"])

        def finalize() -> None:
            self._clear_results()
            if payload["summary"]["hold_miss"] == 0:
                ttk.Label(self.results, text="Hold-Miss: 0 (no exceptions)", font=("Segoe UI", 11, "bold")).pack(anchor="w")
            else:
                self._render_violations(payload.get("violations", []))
            self._render_all_reviewed(payload.get("groups", {}))
            self.footer_time.configure(text=f"Time: {elapsed:.1f}s")
            self._after_finish()

        self._animate_pages(payload.get("pages", 1), finalize)

    # ------------------------------------------------------------------
    # Clipboard / file actions
    def _require_payload(self) -> dict:
        payload = self.state.get("last_payload")
        if not payload:
            raise RuntimeError("No checklist available yet. Run Quick Check or Run Audit first.")
        if "ok" in payload:
            raise RuntimeError("PDF preview does not produce an exportable checklist yet.")
        return payload

    def _copy_txt(self) -> None:
        try:
            payload = self._require_payload()
            txt = payload.get("txt_preview", "")
            if not txt:
                raise RuntimeError("No TXT preview available.")
            self.root.clipboard_clear()
            self.root.clipboard_append(txt)
            self.root.update()
            messagebox.showinfo("HushDesk", "Checklist copied to clipboard.")
        except Exception as exc:
            messagebox.showerror("HushDesk", f"Copy failed:\n{exc}")

    def _save_txt(self) -> None:
        try:
            payload = self._require_payload()
            default_name = f"bp_audit_{payload['header']['date_str']}_{payload['header']['hall'].lower()}_gui.txt"
            out_path = filedialog.asksaveasfilename(defaultextension=".txt", initialfile=default_name, title="Save checklist")
            if not out_path:
                return
            from hushdesk.core.export.checklist_render import write_txt

            write_txt(str(out_path), payload["header"], payload["summary"], payload["sections"])
            messagebox.showinfo("HushDesk", f"Saved: {out_path}")
        except Exception as exc:
            messagebox.showerror("HushDesk", f"Save failed:\n{exc}")


def main() -> None:  # pragma: no cover - UI entry point
    if DND_OK and TkinterDnD is not None:
        root = TkinterDnD.Tk()  # type: ignore[call-arg]
    else:
        root = tk.Tk()
    app = HushDeskApp(root)
    root.mainloop()


if __name__ == "__main__":  # pragma: no cover
    main()




