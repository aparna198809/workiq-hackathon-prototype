r"""
Local Work IQ Simulator — MCP stdio server (scenario-driven).

Metadata
--------
Created:   14-JUN-2026
Component: server.py
Role:      Exposes the EXACT real Work IQ tool contract (`ask_work_iq`) plus the Tools
           surface the challenges need (`fetch`, `create_entity`, `update_entity`) over
           MCP stdio, backed by the synthetic engine. Drop-in replacement for the real
           `workiq` MCP server: participants only swap the `command`/`args` in their MCP
           config — the tool names and shapes are identical.

Environment
-----------
  WORKIQ_SIM_SCENARIO   Absolute or relative path to the scenario dir.
                        Default: scenarios/c1-northbridge (next to this file).
  WORKIQ_SIM_PERSONA    Active persona id for permission trimming
                        (ops_director | quality_pm | credentialing_lead | vendor_liaison).
                        Default: quality_pm. Unset/"all" => full visibility.
  OPENAI_API_KEY/...    Optional. Enables LLM fallback for ad-hoc (non-golden) questions.

Run:
    .\.venv\Scripts\python.exe simulator\server.py
Register in an MCP client (e.g. Copilot CLI) with command=python, args=[server.py].
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

SERVER_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SERVER_DIR))

import engine  # noqa: E402
import proposal_scoring  # noqa: E402
from mcp.server.fastmcp import FastMCP  # noqa: E402

# Import reconciliation agent for approval flow
AGENT_DIR = Path(__file__).resolve().parent.parent / "agent"
sys.path.insert(0, str(AGENT_DIR))
sys.path.insert(0, str(AGENT_DIR / "subagents"))
import reconciliation_agent  # noqa: E402
import proposal_eval_agent  # noqa: E402


def _scenario_dir() -> Path:
    raw = os.environ.get("WORKIQ_SIM_SCENARIO")
    if raw:
        p = Path(raw)
        return p if p.is_absolute() else (SERVER_DIR / p)
    return SERVER_DIR / "scenarios" / "c1-northbridge"


def _persona() -> str | None:
    p = os.environ.get("WORKIQ_SIM_PERSONA", "quality_pm")
    if not p or p.lower() == "all":
        return None
    return p


SCENARIO = engine.load_scenario(_scenario_dir())
PERSONA = _persona()
PERSON_ID = engine._person_id_for(SCENARIO, PERSONA)

mcp = FastMCP("workiq-simulator")


@mcp.tool()
def ask_work_iq(question: str, fileUrls: list[str] | None = None) -> str:
    """Ask a question to Microsoft 365 Copilot (Work IQ).

    Grounds the answer in the active persona's work context (email, meetings, chats,
    files, people, and the Dataverse milestone tracker). Returns JSON with 'response'
    (the answer), the 'conversationId', and 'citations' back to the source signals.

    This mirrors the real Work IQ `ask_work_iq` contract exactly so the simulator is a
    drop-in backend; `fileUrls` is accepted for contract parity (unused in the sim).
    """
    result = engine.ask(SCENARIO, question, persona_id=PERSONA)
    payload = {
        "source": result.get("source", "unknown"),
        "response": result["response"],
        "conversationId": result["conversationId"],
        "citations": result["citations"],
    }
    if result.get("tool"):
        payload["tool_hint"] = result["tool"]
    return json.dumps(payload, indent=2)


@mcp.tool()
def fetch(table: str, filter: dict[str, Any] | None = None) -> str:
    """Low-level table read — use ONLY for write-operation pre-reads (before
    create_entity/update_entity) or when you need raw row data to supplement an
    ask_work_iq answer. For ANSWERING user questions, ALWAYS use ask_work_iq
    first — it searches across emails, meetings, files, AND tables together and
    returns citations. fetch() returns raw rows WITHOUT citations.
    Optionally filter by substring field match. Returns JSON list of rows.
    Results are filtered by the active persona's ACL permissions."""
    try:
        rows = engine.fetch(SCENARIO, table, filter)
    except ValueError as e:
        return _table_error(e)
    # RBAC: only return rows the active persona is authorized to see
    visible = [r for r in rows if engine.can_see(r, PERSONA, PERSON_ID)]
    trimmed = len(rows) - len(visible)
    result = {"rows": visible, "count": len(visible)}
    if trimmed:
        result["_rbac_note"] = f"{trimmed} row(s) withheld due to access restrictions for the active persona."
    return json.dumps(result, indent=2)


@mcp.tool()
def create_entity(table: str, record: dict[str, Any]) -> str:
    """Create (append) a row in a Work IQ Tools-backed table — e.g. open a tracked risk
    item in the Dataverse milestone tracker. Idempotent: re-creating the same logical
    row (same id, or same milestone+owner) returns the existing row instead of
    duplicating. Returns JSON describing whether a row was created.
    The active persona must have ACL permission on the target table."""
    # RBAC: check if persona has write access (can see existing rows in the table)
    if PERSONA:
        existing_rows = SCENARIO.tables.get(table, [])
        if existing_rows and not any(engine.can_see(r, PERSONA, PERSON_ID) for r in existing_rows):
            return json.dumps({
                "created": False,
                "reason": "access_denied",
                "detail": f"Active persona '{PERSONA}' does not have permission to write to '{table}'.",
            }, indent=2)
    try:
        res = engine.create_entity(SCENARIO, table, record, persist=True)
    except ValueError as e:
        return _table_error(e)
    return json.dumps(res, indent=2)


@mcp.tool()
def update_entity(table: str, id: str, patch: dict[str, Any]) -> str:
    """Patch fields on an existing row (by id) in a Work IQ Tools-backed table — e.g.
    move a milestone date or change a status. Returns JSON describing the update.
    The active persona must have ACL permission on the target row."""
    # RBAC: check if persona can see (and therefore modify) the target row
    if PERSONA:
        entry = SCENARIO.index.get(id)
        if entry is not None:
            _, record = entry
            if not engine.can_see(record, PERSONA, PERSON_ID):
                return json.dumps({
                    "updated": False,
                    "reason": "access_denied",
                    "detail": f"Active persona '{PERSONA}' does not have permission to modify row '{id}'.",
                }, indent=2)
    try:
        res = engine.update_entity(SCENARIO, table, id, patch, persist=True)
    except ValueError as e:
        return _table_error(e)
    return json.dumps(res, indent=2)


@mcp.tool()
def generate_report(report_type: str) -> str:
    """Generate a formatted Excel report and return a download link.

    Available report_type values:
      - "weekly_vendor_status"  — Weekly Vendor & Commitment Status report
      - "jc_readiness"          — Joint Commission Readiness Report (vendor compliance)

    Returns JSON with 'download_url' (relative path to fetch the file) and 'filename'.
    Access is governed by the same RBAC rules as the underlying data — the active
    persona must have ACL permission on the relevant table rows.
    """
    REPORTS_DIR = SERVER_DIR / "reports"
    REPORTS_DIR.mkdir(exist_ok=True)

    report_type_lower = report_type.strip().lower().replace(" ", "_").replace("-", "_")
    scenario_dir = _scenario_dir()
    persona = PERSONA or "ops_director"
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")

    # ── RBAC gate: check if persona can see any rows in the target table ──
    REPORT_TABLE_MAP = {
        "weekly_vendor_status": "vendor_contract_tracker",
        "weekly_vendor": "vendor_contract_tracker",
        "vendor_status": "vendor_contract_tracker",
        "weekly_status": "vendor_contract_tracker",
        "jc_readiness": "vendor_contract_tracker",
        "joint_commission": "vendor_contract_tracker",
        "jc_readiness_report": "vendor_contract_tracker",
        "readiness": "vendor_contract_tracker",
    }
    target_table = REPORT_TABLE_MAP.get(report_type_lower)
    if target_table and PERSONA:
        rows = SCENARIO.tables.get(target_table, [])
        visible = [r for r in rows if engine.can_see(r, PERSONA, PERSON_ID)]
        if not visible:
            persona_obj = SCENARIO.get_persona(PERSONA)
            label = persona_obj["label"] if persona_obj else PERSONA
            return json.dumps({
                "error": "Access denied",
                "message": (
                    f"The active persona ({label}) does not have permission to "
                    f"access {target_table} data. This report is restricted to "
                    f"personas with the appropriate ACL clearance."
                ),
                "persona": PERSONA,
                "required_acl": sorted({p for r in rows for p in r.get("acl", ["all"])}),
            }, indent=2)

    if report_type_lower in ("weekly_vendor_status", "weekly_vendor", "vendor_status", "weekly_status"):
        from generate_weekly_vendor_report import generate
        filename = f"Weekly_Vendor_Status_Report_{timestamp}.xlsx"
        out_path = REPORTS_DIR / filename
        generate(scenario_dir, persona, out_path)
    elif report_type_lower in ("jc_readiness", "joint_commission", "jc_readiness_report", "readiness"):
        from generate_jc_readiness_report import generate
        filename = f"JC_Readiness_Report_{timestamp}.xlsx"
        out_path = REPORTS_DIR / filename
        generate(scenario_dir, persona, out_path)
    else:
        return json.dumps({
            "error": f"Unknown report_type: {report_type}",
            "available_reports": ["weekly_vendor_status", "jc_readiness"],
        }, indent=2)

    return json.dumps({
        "status": "success",
        "filename": filename,
        "download_url": f"/download/report/{filename}",
        "message": f"Report generated successfully: {filename}",
        "persona": persona,
        "note": "Report contains only data visible to the active persona per RBAC policy.",
    }, indent=2)


def _table_error(exc: Exception) -> str:
    """Return a structured error an LLM agent can self-correct from."""
    return json.dumps(
        {"error": str(exc), "available_tables": SCENARIO.table_names()},
        indent=2,
    )


# --------------------------------------------------------------------------- #
# CAPA Reconciliation & Approval Flow tools
# --------------------------------------------------------------------------- #

@mcp.tool()
def check_new_action_items() -> str:
    """Check for new action items from recently changed meetings, Teams messages,
    or files. Compares them against open CAPA tracker entries and generates proposals
    (create or update) for human approval.
    
    Call this after data changes are detected to see what reconciliation actions are
    recommended. Returns a list of pending proposals."""
    proposals = reconciliation_agent.process_change_events(SCENARIO)
    if not proposals:
        # Still return any existing pending proposals
        pending = reconciliation_agent.get_pending_proposals()
        if pending:
            return json.dumps({
                "message": "No new changes detected, but there are existing pending proposals.",
                "pending_proposals": pending,
                "count": len(pending),
            }, indent=2)
        return json.dumps({
            "message": "No new action items detected and no pending proposals.",
            "pending_proposals": [],
            "count": 0,
        }, indent=2)

    return json.dumps({
        "message": f"Found {len(proposals)} new proposal(s) from recent changes.",
        "pending_proposals": reconciliation_agent.get_pending_proposals(),
        "count": len(proposals),
    }, indent=2)


@mcp.tool()
def list_pending_approvals() -> str:
    """List all CAPA tracker proposals awaiting approval. Each proposal is either
    a 'create' (new CAPA item) or an 'update' (modify existing CAPA). Review these
    and use approve_proposal or reject_proposal to act on them."""
    pending = reconciliation_agent.get_pending_proposals()
    return json.dumps({
        "pending_proposals": pending,
        "count": len(pending),
    }, indent=2)


@mcp.tool()
def approve_proposal(proposal_id: str, modifications: dict[str, Any] | None = None) -> str:
    """Approve a pending CAPA proposal and execute the create or update operation.
    The active persona is recorded as the approver in the audit trail (created_by
    or modified_by field).
    
    Args:
        proposal_id: The proposal ID to approve (e.g. "PROP-001").
        modifications: Optional dict of field overrides before execution.
    
    Returns JSON with the operation result."""
    # Resolve who is approving
    approver = reconciliation_agent.resolve_persona_to_person(PERSONA, SCENARIO)

    # RBAC: check that persona can write to capa_tracker
    if PERSONA:
        existing_rows = SCENARIO.tables.get("capa_tracker", [])
        if existing_rows and not any(engine.can_see(r, PERSONA, PERSON_ID) for r in existing_rows):
            return json.dumps({
                "approved": False,
                "reason": "access_denied",
                "detail": f"Active persona '{PERSONA}' does not have permission to write to 'capa_tracker'.",
            }, indent=2)

    result = reconciliation_agent.approve_proposal(
        proposal_id=proposal_id,
        sc=SCENARIO,
        approved_by=approver,
        modifications=modifications,
    )
    return json.dumps(result, indent=2)


@mcp.tool()
def reject_proposal(proposal_id: str) -> str:
    """Reject a pending CAPA proposal. The proposed action will NOT be executed.
    
    Args:
        proposal_id: The proposal ID to reject (e.g. "PROP-001").
    
    Returns JSON confirming rejection."""
    result = reconciliation_agent.reject_proposal(proposal_id)
    return json.dumps(result, indent=2)


# --------------------------------------------------------------------------- #
# Vendor Proposal Scoring tools
# --------------------------------------------------------------------------- #

@mcp.tool()
def score_vendor_proposal(rfp_id: str, vendor_contact: str) -> str:
    """Score a single vendor proposal against the weighted evaluation criteria matrix.

    Reads the vendor's proposal emails and documents, extracts key data points
    (cost, SLA, compliance, etc.), and scores each criterion 1-10. Writes the
    result to the vendor_proposal_tracker table with citation trails.

    Args:
        rfp_id: The RFP identifier (e.g. "RFP-001", "RFP-002", "RFP-003").
        vendor_contact: The person ID of the vendor contact (e.g. "PPL-016").

    Returns JSON with the scored proposal including individual scores, weighted
    total, justification, risk flags, and scoring_citations (list of source IDs
    used to compute the scores).
    """
    result = proposal_scoring.score_single_proposal(
        SCENARIO, rfp_id, vendor_contact, persona_id=PERSONA,
    )
    if "error" in result:
        return json.dumps(result, indent=2)

    # Persist to tracker
    proposal_scoring._persist_scores(SCENARIO, [result])

    return json.dumps({
        "status": "scored",
        "proposal": result,
        "scoring_criteria_weights": {
            "Cost & TCO": "20%",
            "Technical Capability": "20%",
            "Performance & SLA": "15%",
            "Compliance & Security": "15%",
            "Implementation Plan": "10%",
            "Vendor Stability": "10%",
            "Innovation & Roadmap": "10%",
        },
    }, indent=2)


@mcp.tool()
def score_all_proposals(rfp_id: str | None = None) -> str:
    """Score and rank all vendor proposals, optionally filtered by RFP.

    For each proposal, reads emails and documents, extracts data, scores against
    the weighted criteria matrix, ranks by weighted total, and persists to the
    vendor_proposal_tracker table with citation trails.

    Args:
        rfp_id: Optional. Score proposals for a specific RFP (e.g. "RFP-001").
                If omitted, scores ALL proposals across ALL RFPs.

    Returns JSON with ranked proposals per RFP, including scores, justifications,
    risk flags, and scoring_citations for audit trail.
    """
    if rfp_id:
        scored = proposal_scoring.score_all_proposals_for_rfp(
            SCENARIO, rfp_id, persona_id=PERSONA, persist=True,
        )
        results = {rfp_id: scored} if scored else {}
    else:
        results = proposal_scoring.score_all_rfps(
            SCENARIO, persona_id=PERSONA, persist=True,
        )

    # Build summary
    summary = []
    for rid, rows in results.items():
        for row in rows:
            summary.append({
                "rfp_id": rid,
                "rank": row.get("rank", 0),
                "vendor_name": row.get("vendor_name", ""),
                "weighted_total": row.get("weighted_total", 0),
                "status": row.get("status", ""),
                "risk_flags": row.get("risk_flags", ""),
                "scoring_citations": row.get("scoring_citations", []),
            })

    return json.dumps({
        "status": "scored",
        "total_proposals_scored": sum(len(r) for r in results.values()),
        "rfps_scored": list(results.keys()),
        "rankings": summary,
        "full_results": results,
        "scoring_criteria_weights": {
            "Cost & TCO": "20%",
            "Technical Capability": "20%",
            "Performance & SLA": "15%",
            "Compliance & Security": "15%",
            "Implementation Plan": "10%",
            "Vendor Stability": "10%",
            "Innovation & Roadmap": "10%",
        },
    }, indent=2)


# --------------------------------------------------------------------------- #
# Proposal Evaluation Agent tools — CDC-driven re-scoring
# --------------------------------------------------------------------------- #

@mcp.tool()
def evaluate_proposals() -> str:
    """Scan for new incoming emails, Teams messages, and meetings related to
    vendor proposals. For each new piece of evidence found:
      1. Identifies which RFP and vendor it relates to
      2. Re-gathers all evidence using AI Search (semantic retrieval)
      3. Re-scores affected proposals against the weighted criteria matrix
      4. Updates the vendor_proposal_tracker table with new scores and citations

    Call this whenever you suspect new proposal-related content has arrived,
    or when the user asks to "re-evaluate", "refresh scores", "check for new
    proposals", or "what's changed in the RFP responses".

    Returns JSON with:
      - events: list of new proposal-related content detected
      - rescored: list of proposals that were re-scored, with old/new scores
        and the new evidence citations that triggered the change
    """
    result = proposal_eval_agent.evaluate_and_rescore(
        SCENARIO, persona_id=PERSONA,
    )
    return json.dumps(result, indent=2)


@mcp.tool()
def get_proposal_evaluation_log() -> str:
    """Return the full evaluation event log — every piece of evidence the
    proposal evaluation agent has detected across all RFPs. Useful for
    audit trail and understanding what informed the current scores.

    Returns JSON list of events with source IDs, types, and timestamps.
    """
    history = proposal_eval_agent.get_evaluation_history()
    return json.dumps({
        "evaluation_events": history,
        "count": len(history),
    }, indent=2)


if __name__ == "__main__":
    # Startup diagnostics go to stderr so they don't corrupt the stdio JSON-RPC stream.
    if PERSONA and PERSONA not in SCENARIO.persona_ids():
        print(
            f"[workiq-simulator][WARN] persona '{PERSONA}' is not defined in this scenario; "
            f"it will see only public (acl=all) content. Valid personas: {SCENARIO.persona_ids()}",
            file=sys.stderr,
        )
    if not SCENARIO.golden:
        print(
            "[workiq-simulator][WARN] scenario loaded 0 golden answers — check "
            "WORKIQ_SIM_SCENARIO points at a populated scenario directory.",
            file=sys.stderr,
        )
    print(
        f"[workiq-simulator] scenario={SCENARIO.root.name} persona={PERSONA or 'all'} "
        f"golden={len(SCENARIO.golden)} tools=ask_work_iq,fetch,create_entity,update_entity,"
        f"generate_report,check_new_action_items,list_pending_approvals,approve_proposal,reject_proposal,"
        f"score_vendor_proposal,score_all_proposals,"
        f"evaluate_proposals,get_proposal_evaluation_log",
        file=sys.stderr,
    )
    mcp.run()
