from __future__ import annotations

import compileall
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Tuple


def run_compile_check() -> bool:
    return compileall.compile_dir("src", force=True, quiet=1)


def preflight_imports() -> Dict[str, bool]:
    modules = ("fitz", "pdfplumber", "tkinterdnd2")
    status: Dict[str, bool] = {}
    for name in modules:
        try:
            __import__(name)
            status[name] = True
        except Exception:
            status[name] = False
    return status


def pdf_open_test(tmp_dir: Path) -> Tuple[bool, str]:
    try:
        import fitz  # PyMuPDF
    except Exception as exc:  # pragma: no cover - module missing
        return False, f"fitz not available ({exc})"

    from hushdesk.pdf.backends import PdfUnavailable, get_backend

    pdf_path = tmp_dir / "auto_smoke.pdf"
    try:
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "HushDesk Auto Smoke")
        doc.save(pdf_path)
        doc.close()

        backend = get_backend()
        opened = backend.open(str(pdf_path))
        closer = getattr(opened, "close", None)
        if callable(closer):
            closer()
        return True, backend.__class__.__name__
    except PdfUnavailable as exc:
        return False, f"backend unavailable ({exc})"
    except Exception as exc:
        return False, f"open failed ({exc})"


def resolve_fixture(filename: str) -> Path | None:
    import importlib.resources as pkg_resources
    import sys

    base_meipass = getattr(sys, "_MEIPASS", None)
    if base_meipass:
        candidate = Path(base_meipass) / "fixtures" / filename
        if candidate.exists():
            return candidate

    try:
        with pkg_resources.as_file(pkg_resources.files("hushdesk").joinpath("fixtures", filename)) as res_path:
            if res_path.exists():
                return res_path
    except Exception:
        pass

    project_root = Path(__file__).resolve().parents[1]
    repo_candidate = project_root / "fixtures" / filename
    if repo_candidate.exists():
        return repo_candidate

    package_candidate = project_root / "src" / "hushdesk" / "fixtures" / filename
    if package_candidate.exists():
        return package_candidate
    return None


def fixture_pipeline(dist_dir: Path) -> Tuple[Dict[str, int], Path | None]:
    from hushdesk.core.engine import run_sim
    from hushdesk.core.export.checklist_render import write_txt

    fixture_path = resolve_fixture("bridgeman_sample.json")
    if not fixture_path:
        return {}, None

    payload = run_sim.run_from_fixture(str(fixture_path))
    summary = payload.get("summary", {})
    header = payload.get("header", {})
    sections = payload.get("sections", [])

    dist_dir.mkdir(parents=True, exist_ok=True)
    txt_path = dist_dir / "bridgeman_auto_smoke.txt"
    write_txt(str(txt_path), header, summary, sections)
    return summary, txt_path


def write_ship_report(
    compile_ok: bool,
    preflight: Dict[str, bool],
    pdf_ok: bool,
    pdf_details: str,
    fixture_summary: Dict[str, int],
    txt_path: Path | None,
    build_path: Path,
    phrase_status: str,
    phrase_results: Dict[str, str],
) -> None:
    tick = lambda ok: "✓" if ok else "✗"
    timestamp = datetime.now(timezone.utc).astimezone().isoformat()
    lines = [
        "# HushDesk Auto Smoke",
        "",
        f"- Run timestamp: {timestamp}",
        f"- Compile check: {tick(compile_ok)}",
        f"- Preflight: fitz {tick(preflight.get('fitz', False))}, "
        f"pdfplumber {tick(preflight.get('pdfplumber', False))}, "
        f"tkinterdnd2 {tick(preflight.get('tkinterdnd2', False))}",
        f"- PDF backend open: {'PASS' if pdf_ok else 'FAIL'} ({pdf_details})",
        f"- Fixture summary: {json.dumps(fixture_summary, sort_keys=True)}",
        f"- TXT output: {txt_path if txt_path else 'not generated'}",
        f"- Build artifact: {build_path} ({'present' if build_path.exists() else 'missing'})",
    ]
    lines.extend(
        [
            "",
            "### Rules Phrase Support",
            f"Status: {phrase_status}",
            "Samples:",
            json.dumps(phrase_results, sort_keys=True),
        ]
    )
    Path("SHIP_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    compile_ok = run_compile_check()
    preflight = preflight_imports()

    dist_dir = Path("dist") / "auto_smoke"
    dist_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        pdf_ok, pdf_details = pdf_open_test(Path(tmp))

    fixture_summary, txt_path = fixture_pipeline(dist_dir)

    build_path = Path("dist") / "HushDesk" / "HushDesk.exe"

    # --- Rules phrase acceptance (headless) ---
    try:
        from hushdesk.core.rules.langmap import normalize_rule_text

        samples = {
            "Hold if SBP less than 90": "SBP < 90",
            "Hold SBP greater than 180": "SBP > 180",
            "Hold if Pulse less than 60": "HR < 60",
        }
        phrase_results = {s: normalize_rule_text(s) for s in samples}
        phrase_ok = all(exp in phrase_results[src] for src, exp in samples.items())
        phrase_status = "OK" if phrase_ok else "FAIL"
    except Exception as e:
        phrase_results = {"error": str(e)}
        phrase_status = "ERROR"

    write_ship_report(
        compile_ok,
        preflight,
        pdf_ok,
        pdf_details,
        fixture_summary,
        txt_path,
        build_path,
        phrase_status,
        phrase_results,
    )


if __name__ == "__main__":
    main()
