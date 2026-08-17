"""
Proposal Evaluation Agent — CDC-driven vendor proposal monitoring and re-scoring.

Watches the engine's change_queue for new emails, Teams messages, meetings, and
files related to vendor proposals. When new content arrives:
  1. Identifies which RFP/vendor the content relates to
  2. Re-gathers proposal evidence using AI Search (semantic) + direct scan
  3. Re-scores affected proposals against the weighted criteria matrix
  4. Updates the vendor_proposal_tracker table with new scores and citations

Works alongside the reconciliation_agent (which handles CAPAs). Both consume
the same change_queue — this agent filters for proposal-related events.
"""
from __future__ import annotations

import re
import sys
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "simulator"))

import engine  # noqa: E402
import proposal_scoring  # noqa: E402
import search_client as _search  # noqa: E402


# --------------------------------------------------------------------------- #
# Evaluation event model
# --------------------------------------------------------------------------- #

@dataclass
class EvalEvent:
    """A detected change relevant to vendor proposal evaluation."""
    event_type: Literal["new_proposal", "updated_proposal", "new_reference", "meeting_insight"]
    rfp_id: str
    vendor_name: str | None = None
    vendor_contact: str | None = None
    source_id: str = ""
    source_type: str = ""
    summary: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))


# Module-level event log
eval_event_log: deque[EvalEvent] = deque(maxlen=200)

# RFP thread IDs for matching
RFP_THREADS = {
    "THR-RFP-TELEHEALTH": "RFP-001",
    "THR-RFP-ANALYTICS": "RFP-002",
    "THR-RFP-WASTE": "RFP-003",
    "THR-RFP-EVAL-INTERNAL": None,  # internal eval discussion
}

# Vendor contact -> RFP mapping (built dynamically from tracker)
_vendor_rfp_cache: dict[str, str] = {}


def _build_vendor_rfp_map(sc: engine.Scenario) -> dict[str, str]:
    """Build vendor_contact -> rfp_id mapping from the tracker table."""
    global _vendor_rfp_cache
    tracker = sc.tables.get("vendor_proposal_tracker", [])
    _vendor_rfp_cache = {
        row["vendor_contact"]: row["rfp_id"]
        for row in tracker
        if "vendor_contact" in row and "rfp_id" in row
    }
    return _vendor_rfp_cache


def _resolve_vendor_name(sc: engine.Scenario, vendor_contact: str) -> str:
    """Get vendor company name from person ID."""
    entry = sc.index.get(vendor_contact)
    if entry:
        _, person = entry
        dept = person.get("department", "")
        if "Vendor" in dept:
            return dept.replace("Vendor (", "").rstrip(")")
    return ""


# --------------------------------------------------------------------------- #
# Change detection — identify proposal-related events
# --------------------------------------------------------------------------- #

def _is_proposal_email(email: dict, sc: engine.Scenario) -> tuple[bool, str | None]:
    """Check if an email is a vendor proposal or RFP-related. Returns (is_proposal, rfp_id)."""
    thread = email.get("thread_id", "")
    if thread in RFP_THREADS:
        return True, RFP_THREADS[thread]

    subject = email.get("subject", "").lower()
    body = email.get("body", "").lower()
    combined = subject + " " + body

    for rfp_id in ("RFP-001", "RFP-002", "RFP-003"):
        if rfp_id.lower() in combined or rfp_id.lower().replace("-", "") in combined.replace("-", ""):
            return True, rfp_id

    # Check if sender is a known vendor contact
    sender = email.get("from", "")
    rfp_map = _vendor_rfp_cache or _build_vendor_rfp_map(sc)
    if sender in rfp_map:
        return True, rfp_map[sender]

    # Keywords that suggest proposal content
    proposal_keywords = ["proposal", "rfp", "telehealth", "analytics", "waste management",
                         "pricing", "sla", "compliance", "implementation"]
    if sum(1 for k in proposal_keywords if k in combined) >= 3:
        return True, None

    return False, None


def _is_proposal_message(msg: dict, sc: engine.Scenario) -> tuple[bool, str | None]:
    """Check if a Teams message is RFP/proposal-related."""
    channel = msg.get("channel", "").lower()
    text = msg.get("text", "").lower()

    if "procurement" in channel or "rfp" in channel:
        return True, None

    for rfp_id in ("RFP-001", "RFP-002", "RFP-003"):
        if rfp_id.lower() in text or rfp_id.lower().replace("-", "") in text.replace("-", ""):
            return True, rfp_id

    # Check for vendor name mentions
    tracker = sc.tables.get("vendor_proposal_tracker", [])
    for row in tracker:
        vname = row.get("vendor_name", "")
        if vname and vname.lower() in text:
            return True, row.get("rfp_id")

    return False, None


def _is_proposal_meeting(meeting: dict, sc: engine.Scenario) -> tuple[bool, str | None]:
    """Check if a meeting is related to vendor evaluation."""
    title = meeting.get("title", "").lower()
    recap = meeting.get("recap", "").lower()
    committee = meeting.get("committee", "")

    if committee == "vendor_review":
        return True, None

    keywords = ["vendor evaluation", "rfp", "proposal", "shortlist", "scoring",
                "procurement", "vendor demo", "vendor presentation"]
    if any(k in title for k in keywords) or any(k in recap for k in keywords):
        return True, None

    return False, None


# --------------------------------------------------------------------------- #
# Core: process changes and re-score
# --------------------------------------------------------------------------- #

def scan_for_proposal_changes(sc: engine.Scenario) -> list[EvalEvent]:
    """Scan the change_queue for proposal-related events. Non-destructive peek
    (the reconciliation agent also needs these events for CAPA matching)."""
    events: list[EvalEvent] = []
    rfp_map = _build_vendor_rfp_map(sc)

    # Scan recent emails for new proposals
    for email in sc.emails:
        is_prop, rfp_id = _is_proposal_email(email, sc)
        if not is_prop:
            continue

        sender = email.get("from", "")
        vendor_name = _resolve_vendor_name(sc, sender)
        sender_rfp = rfp_map.get(sender) or rfp_id

        if vendor_name and sender_rfp:
            event_type = "new_proposal"
        elif rfp_id:
            event_type = "new_reference"
        else:
            event_type = "new_reference"

        events.append(EvalEvent(
            event_type=event_type,
            rfp_id=sender_rfp or rfp_id or "unknown",
            vendor_name=vendor_name or None,
            vendor_contact=sender if vendor_name else None,
            source_id=email["id"],
            source_type="email",
            summary=email.get("subject", ""),
        ))

    # Scan Teams messages
    for msg in sc.teams_messages:
        is_prop, rfp_id = _is_proposal_message(msg, sc)
        if is_prop:
            events.append(EvalEvent(
                event_type="new_reference",
                rfp_id=rfp_id or "unknown",
                source_id=msg["id"],
                source_type="teams_message",
                summary=msg.get("text", "")[:100],
            ))

    # Scan meetings
    for mtg in sc.meetings:
        is_prop, rfp_id = _is_proposal_meeting(mtg, sc)
        if is_prop:
            events.append(EvalEvent(
                event_type="meeting_insight",
                rfp_id=rfp_id or "all",
                source_id=mtg["id"],
                source_type="meeting",
                summary=mtg.get("title", ""),
            ))

    return events


def evaluate_and_rescore(
    sc: engine.Scenario,
    persona_id: str | None = None,
) -> dict:
    """Full evaluation cycle: detect changes, re-score affected proposals, update tracker.

    Returns a summary dict with events detected, proposals re-scored, and changes made.
    """
    events = scan_for_proposal_changes(sc)
    if not events:
        return {
            "status": "no_changes",
            "message": "No new proposal-related content detected.",
            "events": [],
            "rescored": [],
        }

    # Log events
    for evt in events:
        eval_event_log.append(evt)

    # Determine which RFPs need re-scoring
    rfps_to_rescore: set[str] = set()
    vendors_to_rescore: set[tuple[str, str]] = set()  # (rfp_id, vendor_contact)

    for evt in events:
        if evt.rfp_id and evt.rfp_id != "unknown":
            if evt.vendor_contact:
                vendors_to_rescore.add((evt.rfp_id, evt.vendor_contact))
            rfps_to_rescore.add(evt.rfp_id)

    # Re-score affected proposals
    rescored = []
    if vendors_to_rescore:
        # Score specific vendors that had new content
        for rfp_id, vendor_contact in vendors_to_rescore:
            result = proposal_scoring.score_single_proposal(
                sc, rfp_id, vendor_contact, persona_id,
            )
            if "error" not in result:
                rescored.append(result)
    elif rfps_to_rescore:
        # Score all proposals for affected RFPs
        for rfp_id in rfps_to_rescore:
            if rfp_id == "all" or rfp_id == "unknown":
                # Score everything
                all_results = proposal_scoring.score_all_rfps(sc, persona_id, persist=False)
                for rows in all_results.values():
                    rescored.extend(rows)
                break
            else:
                rows = proposal_scoring.score_all_proposals_for_rfp(
                    sc, rfp_id, persona_id, persist=False,
                )
                rescored.extend(rows)

    # Persist re-scored proposals
    if rescored:
        proposal_scoring._persist_scores(sc, rescored)

    # Build change summary
    changes = []
    existing = {
        (r.get("rfp_id"), r.get("vendor_contact")): r
        for r in sc.tables.get("vendor_proposal_tracker", [])
    }
    for row in rescored:
        key = (row.get("rfp_id"), row.get("vendor_contact"))
        old = existing.get(key)
        old_score = old.get("weighted_total", 0) if old else None
        new_score = row.get("weighted_total", 0)
        changes.append({
            "proposal_id": row.get("id"),
            "vendor_name": row.get("vendor_name"),
            "rfp_id": row.get("rfp_id"),
            "old_score": old_score,
            "new_score": new_score,
            "score_change": round(new_score - old_score, 2) if old_score is not None else None,
            "scoring_citations": row.get("scoring_citations", []),
            "new_evidence": [
                evt.source_id for evt in events
                if evt.rfp_id == row.get("rfp_id")
                and (evt.vendor_contact == row.get("vendor_contact") or evt.vendor_contact is None)
            ],
        })

    return {
        "status": "rescored",
        "message": f"Detected {len(events)} proposal-related events. "
                   f"Re-scored {len(rescored)} proposals across {len(rfps_to_rescore)} RFPs.",
        "events": [
            {
                "event_type": e.event_type,
                "rfp_id": e.rfp_id,
                "vendor_name": e.vendor_name,
                "source_id": e.source_id,
                "source_type": e.source_type,
                "summary": e.summary,
            }
            for e in events
        ],
        "rescored": changes,
    }


def get_evaluation_history() -> list[dict]:
    """Return the evaluation event log for audit."""
    return [
        {
            "event_type": e.event_type,
            "rfp_id": e.rfp_id,
            "vendor_name": e.vendor_name,
            "source_id": e.source_id,
            "source_type": e.source_type,
            "summary": e.summary,
            "timestamp": e.timestamp,
        }
        for e in eval_event_log
    ]
