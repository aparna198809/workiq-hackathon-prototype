r"""
Northbridge (C1) hero-demo — a deterministic, presentation-safe walkthrough.

Why this exists
---------------
The orchestrator agent (`workiq_agent.py` / `web.py`) lets a Foundry LLM *decide*
when to call Work IQ. That is the real product, but a live LLM can stall, reword,
or skip a tool call mid-demo. This script drives the **same Work IQ engine**
directly so the judged story always lands, in order, with citations — no model,
no Foundry endpoint, no network required.

What it proves (the four capability domains + governance)
---------------------------------------------------------
  ACT 1  Context + Chat   : the Joint Commission hero question (Q5), answered with
                            multi-signal synthesis and resolved citations.
  ACT 2  Governance/RBAC  : the SAME question across personas — full (ops_director),
                            redacted-with-note (quality_pm), fail-closed (vendor_liaison).
  ACT 3  Tools (hero act) : fetch the open quality-committee CAPAs, then update_entity
                            to escalate + flag every PAST-DUE one (CAPA-001, CAPA-004),
                            with a before/after table.

Run
---
  .\.venv\Scripts\python.exe agent\hero_demo.py            # full walkthrough
  .\.venv\Scripts\python.exe agent\hero_demo.py --no-color # plain output (logs/CI)

Exit code is 0 only if every act produces its expected result, so this doubles as
a smoke test of the demo path.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SIM_DIR = REPO_ROOT / "simulator"
sys.path.insert(0, str(SIM_DIR))

# Windows consoles default to cp1252 and choke on em-dashes / glyphs in fixtures.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

import engine  # noqa: E402

SCENARIO = SIM_DIR / "scenarios" / "c1-northbridge"
CAPA_TABLE = "capa_tracker"

# The Joint Commission readiness hero question (matches golden Q5).
HERO_QUESTION = (
    "Prep me for the Joint Commission readiness review: what did the quality "
    "committee decide on med-reconciliation, who owns the corrective action, did "
    "credentialing close the related onboarding gap, and what's outstanding?"
)

_USE_COLOR = True


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text


def banner(text: str) -> str:
    return _c("1;36", text)


def act_header(n: int, title: str) -> None:
    print(banner("\n" + "=" * 78))
    print(banner(f"ACT {n} — {title}"))
    print(banner("=" * 78))


def render_answer(result: dict, persona_label: str) -> None:
    print(_c("2", f"\npersona = {persona_label}   "
                  f"source={result.get('source')}   matched={result.get('matched')}"))
    print("-" * 78)
    print(result["response"])
    cits = result["citations"]
    if cits:
        print(_c("1;33", "\nCitations:"))
        for c in cits:
            print(f"  [{c['source_index']}] {c['citation_id']:<10} "
                  f"{_c('2', c['kind']):<20} {c['title']}")
    else:
        print(_c("1;33", "\nCitations: (none — fully withheld for this persona)"))
    if result.get("trimmed"):
        print(_c("1;31", f"\n[Governance] Withheld for this persona: "
                         f"{', '.join(result['trimmed'])}"))


# --------------------------------------------------------------------------- #
# ACT 1 — Context + Chat: the hero question, fully cited                       #
# --------------------------------------------------------------------------- #

def act1_context_chat(sc: "engine.Scenario") -> bool:
    act_header(1, "Context + Chat — the Joint Commission readiness brief")
    print(banner(f"\nQ: {HERO_QUESTION}"))
    result = engine.ask(sc, HERO_QUESTION, persona_id="ops_director")
    render_answer(result, "ops_director (James Whitaker — Director of Clinic Operations)")

    cited = {c["citation_id"] for c in result["citations"]}
    # Multi-signal synthesis: a meeting decision, a corrective action, and a closure.
    expected = {"MTG-001", "CAPA-001", "CAPA-002"}
    ok = expected <= cited and not result.get("trimmed")
    print(_c("1;32" if ok else "1;31",
             f"\n[check] full leadership answer cites {sorted(expected)} "
             f"with nothing withheld -> {'PASS' if ok else 'FAIL'}"))
    return ok


# --------------------------------------------------------------------------- #
# ACT 2 — Governance / RBAC: same question, different identities               #
# --------------------------------------------------------------------------- #

def act2_governance(sc: "engine.Scenario") -> bool:
    act_header(2, "Governance / RBAC — same question, permission-trimmed by identity")
    print(banner(f"\nQ: {HERO_QUESTION}"))
    ok = True

    # quality_pm: an HR-sensitive personnel file (FILE-003) is withheld, but a
    # persona-safe redacted brief is still returned, plus a governance note.
    print(banner("\n----- quality_pm (Maria Delgado — Quality Program Manager) -----"))
    r_pm = engine.ask(sc, HERO_QUESTION, persona_id="quality_pm")
    render_answer(r_pm, "quality_pm")
    pm_ok = ("FILE-003" in (r_pm.get("trimmed") or [])) and bool(r_pm["response"].strip())
    print(_c("1;32" if pm_ok else "1;31",
             f"[check] FILE-003 withheld AND a redacted brief still returned -> "
             f"{'PASS' if pm_ok else 'FAIL'}"))
    ok = ok and pm_ok

    # vendor_liaison: least privilege — no persona-safe variant exists, so the
    # answer fails closed (no prose leaked, all sources withheld).
    print(banner("\n----- vendor_liaison (Tom Becker — Lumina Health Systems) -----"))
    r_vendor = engine.ask(sc, HERO_QUESTION, persona_id="vendor_liaison")
    render_answer(r_vendor, "vendor_liaison")
    vendor_ok = len(r_vendor["citations"]) == 0 and bool(r_vendor.get("trimmed"))
    print(_c("1;32" if vendor_ok else "1;31",
             f"[check] vendor_liaison fails closed — zero citations, sources withheld -> "
             f"{'PASS' if vendor_ok else 'FAIL'}"))
    ok = ok and vendor_ok
    return ok


# --------------------------------------------------------------------------- #
# ACT 3 — Tools (the hero action): escalate every past-due quality CAPA        #
# --------------------------------------------------------------------------- #

def _print_capa_table(rows: list[dict], title: str) -> None:
    print(_c("1;33", f"\n{title}"))
    print(f"  {'ID':<10}{'COMMITTEE':<18}{'STATUS':<12}{'PAST_DUE':<10}{'DUE':<12}ACTION")
    for r in rows:
        print(f"  {r['id']:<10}{r.get('committee',''):<18}{r['status']:<12}"
              f"{str(r['past_due']):<10}{r.get('due_date',''):<12}{r['action']}")


def act3_tools(sc: "engine.Scenario") -> bool:
    act_header(3, "Tools (hero action) — escalate & flag every past-due quality CAPA")

    # Read the full tracker first (the Tools `fetch` surface).
    before = engine.fetch(sc, CAPA_TABLE)
    _print_capa_table(before, "BEFORE — full CAPA tracker:")

    # Target: OPEN corrective actions owned by the Quality Steering Committee.
    open_quality = engine.fetch(
        sc, CAPA_TABLE, {"committee": "quality_steering", "status": "Open"}
    )
    targets = [r["id"] for r in open_quality if r.get("past_due")]
    print(banner(f"\nHero action: for each OPEN quality-committee CAPA that is past due "
                 f"{targets}, call update_entity -> status='Escalated', past_due=True"))

    updated_ids = []
    for cid in targets:
        res = engine.update_entity(
            sc, CAPA_TABLE, cid, {"status": "Escalated", "past_due": True}
        )
        if res.get("updated"):
            updated_ids.append(cid)
            row = res["row"]
            print(_c("2", f"  update_entity({cid}) -> status={row['status']} "
                          f"past_due={row['past_due']}"))

    after = engine.fetch(sc, CAPA_TABLE)
    _print_capa_table(after, "AFTER — full CAPA tracker:")

    # Guardrails: only past-due quality items move; Closed / non-quality / not-yet-due
    # rows are left untouched.
    escalated = {r["id"] for r in after if r["status"] == "Escalated"}
    expected = {"CAPA-001", "CAPA-004"}
    untouched_ok = (
        next(r for r in after if r["id"] == "CAPA-002")["status"] == "Closed"
        and next(r for r in after if r["id"] == "CAPA-003")["status"] == "Open"
    )
    ok = escalated == expected and untouched_ok and set(updated_ids) == expected
    print(_c("1;32" if ok else "1;31",
             f"\n[check] escalated exactly {sorted(expected)}; CAPA-002 (Closed) and "
             f"CAPA-003 (not past due) untouched -> {'PASS' if ok else 'FAIL'}"))
    return ok


def main() -> int:
    global _USE_COLOR
    ap = argparse.ArgumentParser(description="Northbridge C1 deterministic hero demo")
    ap.add_argument("--no-color", action="store_true", help="disable ANSI colour")
    args = ap.parse_args()
    _USE_COLOR = not args.no_color

    sc = engine.load_scenario(SCENARIO)
    print(banner("Northbridge Health Network — Work IQ hero demo (deterministic)"))
    print(_c("2", f"scenario = {SCENARIO.name}   "
                  f"personas = {', '.join(sc.persona_ids())}"))

    results = {
        "ACT 1 Context+Chat": act1_context_chat(sc),
        "ACT 2 Governance/RBAC": act2_governance(sc),
        "ACT 3 Tools (hero action)": act3_tools(sc),
    }

    print(banner("\n" + "=" * 78))
    print(banner("SUMMARY"))
    for name, ok in results.items():
        print(f"  {name:<28} {_c('1;32','PASS') if ok else _c('1;31','FAIL')}")
    all_ok = all(results.values())
    print(banner("=" * 78))
    print(_c("1;32", "\nALL HERO-DEMO CHECKS PASSED") if all_ok
          else _c("1;31", "\nHERO-DEMO HAD FAILURES"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
