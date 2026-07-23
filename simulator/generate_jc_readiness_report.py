"""
Generate the Joint Commission Readiness Report (vendor compliance items) as an Excel file.
Simulates the agent's `generate_report` tool action for Q10.

Usage:
    python generate_jc_readiness_report.py [--persona ops_director] [--out <path>]
"""
from __future__ import annotations
import argparse, json, sys, os
from pathlib import Path
from datetime import datetime

SIM_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SIM_DIR))
import engine  # noqa: E402

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# ── Styles ──────────────────────────────────────────────────
BLUE      = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
LIGHT     = PatternFill(start_color="D6E4F0", end_color="D6E4F0", fill_type="solid")
GREEN_F   = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
AMBER_F   = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
RED_F     = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
WHITE_B   = Font(name="Calibri", bold=True, color="FFFFFF", size=10)
BOLD      = Font(name="Calibri", bold=True, size=10)
NORM      = Font(name="Calibri", size=10)
TITLE     = Font(name="Calibri", bold=True, size=14, color="1F4E79")
SUB       = Font(name="Calibri", bold=True, size=11, color="1F4E79")
BORDER    = Border(*(Side(style="thin"),) * 4)
WRAP      = Alignment(wrap_text=True, vertical="top")


def _header(ws, row, ncols):
    for c in range(1, ncols + 1):
        cell = ws.cell(row=row, column=c)
        cell.font, cell.fill = WHITE_B, BLUE
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER


def _data(ws, r1, r2, ncols):
    for r in range(r1, r2 + 1):
        for c in range(1, ncols + 1):
            cell = ws.cell(row=r, column=c)
            cell.font, cell.alignment, cell.border = NORM, WRAP, BORDER
            if (r - r1) % 2 == 0:
                cell.fill = LIGHT


def _status_fill(val):
    v = str(val).upper()
    if v in ("GO", "GREEN", "ON TRACK", "CLOSED"):
        return GREEN_F
    if v in ("AT RISK", "AMBER"):
        return AMBER_F
    if v in ("PAST DUE", "RED", "BLOCKED"):
        return RED_F
    return None


def _widths(ws, widths):
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def generate(scenario_dir: str | Path, persona_id: str, out_path: str | Path):
    sc = engine.load_scenario(scenario_dir)

    # ── Run Q10 through the engine ──────────────────────────
    result = engine.ask(
        sc,
        "Generate the Joint Commission readiness report focusing on vendor-related compliance items.",
        persona_id=persona_id,
    )
    print(f"[generate_report] matched={result.get('matched')}  source={result.get('source')}  "
          f"citations={len(result.get('citations', []))}  trimmed={len(result.get('trimmed', []))}")

    # ── Pull live data ──────────────────────────────────────
    all_tracker = sc.tables.get("vendor_contract_tracker", [])
    all_capas = sc.tables.get("capa_tracker", [])
    ppl = {p["id"]: p["name"] for p in sc.people}

    # RBAC: only include rows the active persona is authorized to see
    tracker = [r for r in all_tracker if engine.can_see(r, persona_id)]
    capas = [r for r in all_capas if engine.can_see(r, persona_id)]
    print(f"[generate_report] RBAC: {len(tracker)}/{len(all_tracker)} vendor rows, "
          f"{len(capas)}/{len(all_capas)} CAPA rows visible to '{persona_id}'",
          file=sys.stderr)

    if not tracker:
        print("[generate_report] ERROR: vendor_contract_tracker not found or no visible rows", file=sys.stderr)
        sys.exit(1)

    # ── Build workbook ──────────────────────────────────────
    wb = Workbook()
    now = datetime.now().strftime("%d-%b-%Y %H:%M")

    # ====== Sheet 1: JC Readiness Dashboard ======
    ws1 = wb.active
    ws1.title = "JC Readiness Dashboard"
    ws1.merge_cells("A1:F1")
    ws1["A1"].value = f"Joint Commission Readiness Report — Vendor Compliance Items"
    ws1["A1"].font = TITLE
    ws1.merge_cells("A2:F2")
    ws1["A2"].value = f"As of {now}  |  Persona: {persona_id}  |  Scenario: {sc.root.name}"
    ws1["A2"].font = Font(name="Calibri", italic=True, size=9, color="666666")

    # Section 1: Medication Management (JC Standard MM)
    row = 4
    ws1.merge_cells(f"A{row}:F{row}")
    ws1.cell(row=row, column=1, value="1. Medication Management (Joint Commission Standard MM)")
    ws1.cell(row=row, column=1).font = SUB
    row += 1

    h1 = ["Vendor", "Category", "Item", "Status", "Details", "JC Impact"]
    for c, v in enumerate(h1, 1):
        ws1.cell(row=row, column=c, value=v)
    _header(ws1, row, len(h1))
    row += 1

    mm_items = [
        ("Lumina Health Systems", "EHR & Clinical Software",
         "Westgate EHR medication-list data migration",
         "GO", "Validated and signed off", "Medication-management compliance confirmed"),
        ("PharmaLink Distributors", "Clinical Supplies & Pharmacy",
         "Controlled-substance audit log binders",
         "AT RISK", "Delayed to 16-JUL (was 11-JUL). Needed for pharmacy audit cycle due 25-JUL.",
         "SLA clause 5.2 (5% credit/wk) in play if 16-JUL slips"),
        ("ClearPoint Clinical Solutions", "Clinical Software — CPOE & Lab",
         "CPOE v4.2 medication-interaction alerting",
         "ON TRACK", "Confirmed to meet JC medication-management standards (Appendix C). Deployment 21-JUL.",
         "Before survey window — compliant"),
    ]
    mm_start = row
    for vendor, cat, item, status, details, impact in mm_items:
        ws1.cell(row=row, column=1, value=vendor)
        ws1.cell(row=row, column=2, value=cat)
        ws1.cell(row=row, column=3, value=item)
        ws1.cell(row=row, column=4, value=status)
        ws1.cell(row=row, column=5, value=details)
        ws1.cell(row=row, column=6, value=impact)
        sf = _status_fill(status)
        if sf:
            ws1.cell(row=row, column=4).fill = sf
        row += 1
    _data(ws1, mm_start, row - 1, len(h1))
    # Re-apply status fills (since _data may overwrite)
    r = mm_start
    for _, _, _, status, _, _ in mm_items:
        sf = _status_fill(status)
        if sf:
            ws1.cell(row=r, column=4).fill = sf
        r += 1

    # Section 2: Environment of Care — Equipment (JC Standard EC)
    row += 1
    ws1.merge_cells(f"A{row}:F{row}")
    ws1.cell(row=row, column=1, value="2. Environment of Care — Equipment (Joint Commission Standard EC)")
    ws1.cell(row=row, column=1).font = SUB
    row += 1

    for c, v in enumerate(h1, 1):
        ws1.cell(row=row, column=c, value=v)
    _header(ws1, row, len(h1))
    row += 1

    ec_items = [
        ("MediTech Biomedical", "Medical & Biomedical Equipment",
         "Westgate patient-monitor calibration (12 units)",
         "ON TRACK", "Scheduled 14-JUL. Autoclave validation 18-JUL. Certs due by 20-JUL.",
         "EC standard — calibration certificates required"),
        ("(All clinics)", "—",
         "Riverside defibrillator & infusion-pump calibrations",
         "GO", "All complete.",
         "EC standard — fully compliant"),
    ]
    ec_start = row
    for vendor, cat, item, status, details, impact in ec_items:
        ws1.cell(row=row, column=1, value=vendor)
        ws1.cell(row=row, column=2, value=cat)
        ws1.cell(row=row, column=3, value=item)
        ws1.cell(row=row, column=4, value=status)
        ws1.cell(row=row, column=5, value=details)
        ws1.cell(row=row, column=6, value=impact)
        sf = _status_fill(status)
        if sf:
            ws1.cell(row=row, column=4).fill = sf
        row += 1
    _data(ws1, ec_start, row - 1, len(h1))
    r = ec_start
    for _, _, _, status, _, _ in ec_items:
        sf = _status_fill(status)
        if sf:
            ws1.cell(row=r, column=4).fill = sf
        r += 1

    # Section 3: HR / Credentialing
    row += 1
    ws1.merge_cells(f"A{row}:F{row}")
    ws1.cell(row=row, column=1, value="3. Human Resources / Credentialing")
    ws1.cell(row=row, column=1).font = SUB
    row += 1

    for c, v in enumerate(h1, 1):
        ws1.cell(row=row, column=c, value=v)
    _header(ws1, row, len(h1))
    row += 1

    hr_items = [
        ("(Internal)", "Credentialing",
         "Provider-onboarding gap (CAPA-002)",
         "GO", "CLOSED 05-JUN. Primary-source verification backlog cleared.",
         "HR standard — compliant"),
    ]
    hr_start = row
    for vendor, cat, item, status, details, impact in hr_items:
        ws1.cell(row=row, column=1, value=vendor)
        ws1.cell(row=row, column=2, value=cat)
        ws1.cell(row=row, column=3, value=item)
        ws1.cell(row=row, column=4, value=status)
        ws1.cell(row=row, column=5, value=details)
        ws1.cell(row=row, column=6, value=impact)
        sf = _status_fill(status)
        if sf:
            ws1.cell(row=row, column=4).fill = sf
        row += 1
    _data(ws1, hr_start, row - 1, len(h1))
    sf = _status_fill("GO")
    if sf:
        ws1.cell(row=hr_start, column=4).fill = sf

    _widths(ws1, [26, 30, 42, 12, 56, 42])

    # ====== Sheet 2: Open CAPAs on Critical Path ======
    ws2 = wb.create_sheet("CAPAs — Critical Path")
    ws2.merge_cells("A1:G1")
    ws2["A1"].value = "Open CAPAs on Joint Commission Critical Path"
    ws2["A1"].font = TITLE

    h2 = ["CAPA ID", "Action", "Committee", "Owner", "Due Date", "Status", "JC Impact"]
    for c, v in enumerate(h2, 1):
        ws2.cell(row=3, column=c, value=v)
    _header(ws2, 3, len(h2))

    # Filter to open CAPAs
    jc_capa_ids = {"CAPA-001", "CAPA-002", "CAPA-004"}
    jc_capas = [ca for ca in capas if ca["id"] in jc_capa_ids]
    impact_map = {
        "CAPA-001": "Medication-management readiness — not vendor-dependent but affects JC MM standard",
        "CAPA-002": "HR/credentialing — closed, no impact",
        "CAPA-004": "Environment-of-care documentation — blocked on facilities vendor quote for signage",
    }
    row = 4
    for ca in jc_capas:
        due = ca.get("due_date", "")
        is_past_due = ca["status"] not in ("Closed",)
        # Check if past due (simple date comparison)
        try:
            from datetime import date
            if due and date.fromisoformat(due) < date(2026, 7, 14):
                is_past_due = True
        except Exception:
            pass
        display_status = "PAST DUE" if (is_past_due and ca["status"] != "Closed") else ca["status"]
        if ca["status"] == "Closed":
            display_status = "CLOSED"

        ws2.cell(row=row, column=1, value=ca["id"])
        ws2.cell(row=row, column=2, value=ca["action"])
        ws2.cell(row=row, column=3, value=ca["committee"])
        ws2.cell(row=row, column=4, value=ppl.get(ca["owner"], ca["owner"]))
        ws2.cell(row=row, column=5, value=due)
        ws2.cell(row=row, column=6, value=display_status)
        ws2.cell(row=row, column=7, value=impact_map.get(ca["id"], ""))
        sf = _status_fill(display_status)
        if sf:
            ws2.cell(row=row, column=6).fill = sf
        row += 1
    _data(ws2, 4, row - 1, len(h2))
    # Re-apply status fills
    r2 = 4
    for ca in jc_capas:
        due = ca.get("due_date", "")
        display_status = ca["status"]
        try:
            from datetime import date
            if due and date.fromisoformat(due) < date(2026, 7, 14) and ca["status"] != "Closed":
                display_status = "PAST DUE"
        except Exception:
            pass
        if ca["status"] == "Closed":
            display_status = "CLOSED"
        sf = _status_fill(display_status)
        if sf:
            ws2.cell(row=r2, column=6).fill = sf
        r2 += 1

    _widths(ws2, [10, 50, 20, 20, 14, 14, 60])

    # ====== Sheet 3: Vendor Readiness Summary ======
    ws3 = wb.create_sheet("Vendor Readiness")
    ws3.merge_cells("A1:G1")
    ws3["A1"].value = "Vendor Readiness Summary for Joint Commission"
    ws3["A1"].font = TITLE

    h3 = ["VND ID", "Vendor", "Category", "SLA Status", "Compliance Requirements",
          "JC Readiness", "Key Dates"]
    for c, v in enumerate(h3, 1):
        ws3.cell(row=3, column=c, value=v)
    _header(ws3, 3, len(h3))

    readiness_map = {
        "VND-001": ("GREEN", "Data migration validated, go-live completed"),
        "VND-002": ("GREEN", "Calibrations on track, certs due 20-JUL"),
        "VND-003": ("AMBER", "Audit log binders delayed — 16-JUL contingent"),
        "VND-004": ("GREEN", "CPOE v4.2 JC-compliant, deployment 21-JUL"),
    }
    dates_map = {
        "VND-001": "Go-live: 22-JUN (completed)",
        "VND-002": "Calibration: 14-JUL, Autoclave: 18-JUL, Certs: 20-JUL",
        "VND-003": "Audit binders: 16-JUL (delayed from 11-JUL), Pharmacy audit: 25-JUL",
        "VND-004": "Staging: 17-JUL, Production: 21-JUL, HL7: 15-JUL",
    }

    row = 4
    for vnd in tracker:
        jc_status, jc_note = readiness_map.get(vnd["id"], ("—", ""))
        ws3.cell(row=row, column=1, value=vnd["id"])
        ws3.cell(row=row, column=2, value=vnd["vendor_name"])
        ws3.cell(row=row, column=3, value=vnd["category"])
        ws3.cell(row=row, column=4, value=vnd["current_sla_status"])
        comp_req = vnd.get("compliance_requirements", "")
        if isinstance(comp_req, list):
            comp_req = ", ".join(comp_req)
        ws3.cell(row=row, column=5, value=comp_req)
        ws3.cell(row=row, column=6, value=f"{jc_status} — {jc_note}")
        ws3.cell(row=row, column=7, value=dates_map.get(vnd["id"], ""))
        sf = _status_fill(vnd["current_sla_status"])
        if sf:
            ws3.cell(row=row, column=4).fill = sf
        sf2 = _status_fill(jc_status)
        if sf2:
            ws3.cell(row=row, column=6).fill = sf2
        row += 1
    _data(ws3, 4, row - 1, len(h3))
    # Re-apply fills
    r3 = 4
    for vnd in tracker:
        jc_status, _ = readiness_map.get(vnd["id"], ("—", ""))
        sf = _status_fill(vnd["current_sla_status"])
        if sf:
            ws3.cell(row=r3, column=4).fill = sf
        sf2 = _status_fill(jc_status)
        if sf2:
            ws3.cell(row=r3, column=6).fill = sf2
        r3 += 1

    # Summary row
    row += 1
    ws3.merge_cells(f"A{row}:G{row}")
    ws3.cell(row=row, column=1,
             value="Overall: 3 of 4 vendors GREEN, 1 AMBER (PharmaLink). "
                   "All vendor-dependent JC items on track contingent on PharmaLink 16-JUL delivery "
                   "and MediTech 18-JUL autoclave validation.")
    ws3.cell(row=row, column=1).font = BOLD

    _widths(ws3, [10, 28, 30, 12, 40, 44, 50])

    # ====== Sheet 4: JC Standard Mapping ======
    ws4 = wb.create_sheet("JC Standard Mapping")
    ws4.merge_cells("A1:E1")
    ws4["A1"].value = "Vendor ↔ Joint Commission Standard Mapping"
    ws4["A1"].font = TITLE

    h4 = ["JC Standard", "Standard Code", "Vendor(s)", "Compliance Item", "Status"]
    for c, v in enumerate(h4, 1):
        ws4.cell(row=3, column=c, value=v)
    _header(ws4, 3, len(h4))

    jc_rows = [
        ("Medication Management", "MM", "Lumina Health Systems",
         "EHR medication-list data migration", "GO"),
        ("Medication Management", "MM", "PharmaLink Distributors",
         "Controlled-substance audit log binders", "AT RISK"),
        ("Medication Management", "MM", "ClearPoint Clinical Solutions",
         "CPOE v4.2 medication-interaction alerting", "ON TRACK"),
        ("Environment of Care", "EC", "MediTech Biomedical",
         "Patient-monitor calibration & autoclave validation", "ON TRACK"),
        ("Environment of Care", "EC", "(All clinics)",
         "Defibrillator & infusion-pump calibrations", "GO"),
        ("Human Resources", "HR", "(Internal — Credentialing)",
         "Provider-onboarding verification gap (CAPA-002)", "GO"),
    ]
    row = 4
    for std, code, vendor, item, status in jc_rows:
        ws4.cell(row=row, column=1, value=std)
        ws4.cell(row=row, column=2, value=code)
        ws4.cell(row=row, column=3, value=vendor)
        ws4.cell(row=row, column=4, value=item)
        ws4.cell(row=row, column=5, value=status)
        sf = _status_fill(status)
        if sf:
            ws4.cell(row=row, column=5).fill = sf
        row += 1
    _data(ws4, 4, row - 1, len(h4))
    r4 = 4
    for _, _, _, _, status in jc_rows:
        sf = _status_fill(status)
        if sf:
            ws4.cell(row=r4, column=5).fill = sf
        r4 += 1

    _widths(ws4, [24, 14, 30, 44, 12])

    # ====== Sheet 5: Citations ======
    ws5 = wb.create_sheet("Citations")
    ws5.merge_cells("A1:E1")
    ws5["A1"].value = "Report Citations — Sources Used"
    ws5["A1"].font = TITLE

    h5 = ["#", "Citation ID", "Kind", "Title", "Sensitivity"]
    for c, v in enumerate(h5, 1):
        ws5.cell(row=3, column=c, value=v)
    _header(ws5, 3, len(h5))

    for i, cit in enumerate(result.get("citations", [])):
        r = 4 + i
        ws5.cell(row=r, column=1, value=cit["source_index"])
        ws5.cell(row=r, column=2, value=cit["citation_id"])
        ws5.cell(row=r, column=3, value=cit["kind"])
        ws5.cell(row=r, column=4, value=cit["title"])
        ws5.cell(row=r, column=5, value=cit.get("sensitivity", "internal"))
    _data(ws5, 4, 4 + len(result.get("citations", [])) - 1, len(h5))
    _widths(ws5, [6, 12, 18, 60, 12])

    # ── Save ────────────────────────────────────────────────
    wb.save(out_path)
    print(f"[generate_report] Report saved -> {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", default=str(SIM_DIR / "scenarios" / "c1-northbridge"))
    parser.add_argument("--persona", default="ops_director")
    parser.add_argument("--out", default=str(SIM_DIR / "scenarios" / "c1-northbridge" / "tables" /
                                             "JC_Readiness_Report_Vendor_Compliance.xlsx"))
    args = parser.parse_args()
    generate(args.scenario, args.persona, args.out)
