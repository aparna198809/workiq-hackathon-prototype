"""
CAPA Reconciliation Agent — CDC-driven action-item extraction and matching.

Watches the engine's change_queue for new records in meetings, Teams messages,
and files. Extracts action items, compares them against open CAPA tracker entries,
and drafts proposals (create or update) for human approval.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

# Ensure sibling modules are importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "simulator"))

import engine  # noqa: E402


# --------------------------------------------------------------------------- #
# Proposal data model
# --------------------------------------------------------------------------- #

@dataclass
class CAPAProposal:
    """A drafted CAPA create or update awaiting approval."""
    proposal_id: str
    action_type: Literal["create", "update"]
    table: str = "capa_tracker"
    target_id: str | None = None            # for updates — the existing CAPA id
    drafted_record: dict = field(default_factory=dict)   # for creates
    patch: dict = field(default_factory=dict)            # for updates
    source_citations: list[str] = field(default_factory=list)
    notify_roles: list[str] = field(default_factory=list)  # ACL roles to notify
    status: Literal["pending", "approved", "rejected"] = "pending"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    match_reason: str = ""  # why it matched (or why it's new)


# Module-level pending proposals queue
pending_proposals: dict[str, CAPAProposal] = {}

# Auto-increment for proposal IDs
_proposal_counter: int = 0


def _next_proposal_id() -> str:
    global _proposal_counter
    _proposal_counter += 1
    return f"PROP-{_proposal_counter:03d}"


# --------------------------------------------------------------------------- #
# Text similarity — lightweight token overlap for matching action descriptions
# --------------------------------------------------------------------------- #

_STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "for", "and", "nor", "but",
    "or", "yet", "so", "at", "by", "from", "in", "into", "of", "on", "to",
    "with", "that", "this", "it", "its", "as", "if", "then", "than",
}


def _tokenize(text: str) -> set[str]:
    """Lowercase, strip non-alnum, remove stop words."""
    tokens = re.sub(r"[^a-z0-9]+", " ", text.lower()).split()
    return {t for t in tokens if t not in _STOP_WORDS and len(t) > 2}


def text_similarity(a: str, b: str) -> float:
    """Jaccard similarity between tokenized texts."""
    ta, tb = _tokenize(a), _tokenize(b)
    if not ta or not tb:
        return 0.0
    intersection = ta & tb
    union = ta | tb
    return len(intersection) / len(union)


# --------------------------------------------------------------------------- #
# Core reconciliation logic
# --------------------------------------------------------------------------- #

# Thresholds for matching
SIMILARITY_THRESHOLD = 0.35  # text similarity needed to consider a match
OWNER_MATCH_BOOST = 0.2     # bonus if owners match


def extract_action_items_from_meeting(meeting: dict) -> list[dict]:
    """Extract action items from a meeting record."""
    items = []
    for ai in meeting.get("action_items", []):
        if ai.get("status", "").lower() == "closed":
            continue
        items.append({
            "id": ai.get("id"),
            "text": ai.get("text", ""),
            "owner": ai.get("owner"),
            "due": ai.get("due"),
            "source_type": "meeting",
            "source_id": meeting.get("id"),
            "committee": meeting.get("committee"),
            "acl": meeting.get("acl", ["all"]),
        })
    return items


def extract_action_items_from_message(msg: dict) -> list[dict]:
    """Extract potential action items from a Teams message.
    
    Looks for patterns like 'action:', 'TODO:', 'need to', 'must', 'will own',
    or references to CAPA items.
    """
    text = msg.get("text", "")
    items = []

    # Check if message references CAPA actions or contains action language
    capa_refs = re.findall(r"CAPA-\d{3}", text)
    action_patterns = [
        r"(?:action|TODO|task):\s*(.+?)(?:\.|$)",
        r"(?:need to|must|will|should)\s+(.+?)(?:\.|$)",
    ]

    for pattern in action_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            items.append({
                "id": None,
                "text": match.strip(),
                "owner": msg.get("author"),
                "due": None,
                "source_type": "teams_message",
                "source_id": msg.get("id"),
                "committee": None,
                "acl": msg.get("acl", ["all"]),
                "capa_refs": capa_refs,
            })

    return items


def reconcile_action_item(
    action_item: dict,
    open_capas: list[dict],
) -> CAPAProposal:
    """Compare a single action item against open CAPAs and produce a proposal.
    
    Returns either an 'update' proposal (if it matches an existing CAPA) or a
    'create' proposal (if it's a new action).
    """
    ai_text = action_item.get("text", "")
    ai_owner = action_item.get("owner")
    ai_capa_refs = action_item.get("capa_refs", [])

    best_match: dict | None = None
    best_score: float = 0.0

    for capa in open_capas:
        capa_action = capa.get("action", "")
        capa_owner = capa.get("owner")
        capa_id = capa.get("id", "")

        # Direct CAPA reference in the action item text or extracted refs
        if capa_id in ai_text or capa_id in ai_capa_refs:
            best_match = capa
            best_score = 1.0
            break

        # Text similarity + owner match
        sim = text_similarity(ai_text, capa_action)
        if ai_owner and ai_owner == capa_owner:
            sim += OWNER_MATCH_BOOST

        if sim > best_score:
            best_score = sim
            best_match = capa

    source_citations = []
    if action_item.get("source_id"):
        source_citations.append(action_item["source_id"])
    if action_item.get("id"):
        source_citations.append(action_item["id"])

    if best_match and best_score >= SIMILARITY_THRESHOLD:
        # Propose UPDATE to existing CAPA
        patch: dict[str, Any] = {}
        if action_item.get("due") and action_item["due"] != best_match.get("due_date"):
            patch["due_date"] = action_item["due"]
        # If the action item text suggests status change
        ai_lower = ai_text.lower()
        if "flagged" in ai_lower or "escalat" in ai_lower:
            patch["status"] = "Flagged"
        elif "open" in ai_lower or "reopen" in ai_lower:
            patch["status"] = "Open"
        elif "clos" in ai_lower or "complet" in ai_lower:
            patch["status"] = "Closed"
        # If no meaningful patch, at least note the reference
        if not patch:
            patch["status"] = best_match.get("status", "Open")

        proposal = CAPAProposal(
            proposal_id=_next_proposal_id(),
            action_type="update",
            target_id=best_match["id"],
            patch=patch,
            source_citations=source_citations,
            notify_roles=best_match.get("acl", []),
            match_reason=f"Matched existing {best_match['id']} (score={best_score:.2f}, "
                         f"owner={'same' if ai_owner == best_match.get('owner') else 'different'})",
        )
    else:
        # Propose CREATE new CAPA
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        drafted = {
            "action": ai_text,
            "committee": action_item.get("committee", "quality_steering"),
            "owner": ai_owner,
            "status": "Open",
            "opened_date": today,
            "due_date": action_item.get("due") or today,
            "past_due": False,
        }
        if action_item.get("acl"):
            drafted["acl"] = action_item["acl"]

        proposal = CAPAProposal(
            proposal_id=_next_proposal_id(),
            action_type="create",
            drafted_record=drafted,
            source_citations=source_citations,
            notify_roles=action_item.get("acl", []),
            match_reason=f"No matching open CAPA found (best_score={best_score:.2f})",
        )

    return proposal


def process_change_events(sc: engine.Scenario) -> list[CAPAProposal]:
    """Drain the change_queue, extract action items from new records, reconcile
    against open CAPAs, and return a list of proposals."""
    proposals: list[CAPAProposal] = []

    # Get open CAPAs (not Closed)
    capa_rows = sc.tables.get("capa_tracker", [])
    open_capas = [r for r in capa_rows if r.get("status", "").lower() != "closed"]

    # Drain the change queue
    events: list[engine.ChangeEvent] = []
    while engine.change_queue:
        events.append(engine.change_queue.popleft())

    if not events:
        return proposals

    for evt in events:
        new_action_items: list[dict] = []

        if evt.file == "meetings.json":
            # Find the new/modified meetings and extract action items
            for meeting in sc.meetings:
                mid = meeting.get("id", "")
                if mid in evt.added_ids:
                    new_action_items.extend(extract_action_items_from_meeting(meeting))
                else:
                    # Check if any of the meeting's action items are new
                    for ai in meeting.get("action_items", []):
                        if ai.get("id") in evt.added_ids:
                            new_action_items.append({
                                "id": ai.get("id"),
                                "text": ai.get("text", ""),
                                "owner": ai.get("owner"),
                                "due": ai.get("due"),
                                "source_type": "meeting",
                                "source_id": meeting.get("id"),
                                "committee": meeting.get("committee"),
                                "acl": meeting.get("acl", ["all"]),
                            })

        elif evt.file == "teams.json":
            for msg in sc.teams_messages:
                if msg.get("id") in evt.added_ids:
                    extracted = extract_action_items_from_message(msg)
                    new_action_items.extend(extracted)

        # Reconcile each action item against open CAPAs
        for ai in new_action_items:
            proposal = reconcile_action_item(ai, open_capas)
            pending_proposals[proposal.proposal_id] = proposal
            proposals.append(proposal)

    if proposals:
        print(
            f"[reconciliation] Generated {len(proposals)} proposal(s) from "
            f"{len(events)} change event(s)",
            file=sys.stderr,
        )

    return proposals


def get_pending_proposals() -> list[dict]:
    """Return all pending proposals as serializable dicts."""
    return [
        {
            "proposal_id": p.proposal_id,
            "action_type": p.action_type,
            "table": p.table,
            "target_id": p.target_id,
            "drafted_record": p.drafted_record,
            "patch": p.patch,
            "source_citations": p.source_citations,
            "notify_roles": p.notify_roles,
            "status": p.status,
            "created_at": p.created_at,
            "match_reason": p.match_reason,
        }
        for p in pending_proposals.values()
        if p.status == "pending"
    ]


def approve_proposal(
    proposal_id: str,
    sc: engine.Scenario,
    approved_by: str,
    modifications: dict | None = None,
) -> dict:
    """Approve a pending proposal and execute the create/update.
    
    Args:
        proposal_id: The proposal to approve.
        sc: The scenario to write to.
        approved_by: Person ID of the approver (from persona mapping).
        modifications: Optional overrides to apply before execution.
    
    Returns:
        Result dict from the engine operation.
    """
    proposal = pending_proposals.get(proposal_id)
    if not proposal:
        return {"error": "proposal_not_found", "proposal_id": proposal_id}
    if proposal.status != "pending":
        return {"error": "proposal_already_processed", "status": proposal.status}

    if proposal.action_type == "create":
        record = dict(proposal.drafted_record)
        if modifications:
            record.update(modifications)
        result = engine.create_entity(
            sc, proposal.table, record,
            persist=True,
            approved_by=approved_by,
            source_citations=proposal.source_citations,
        )
        if result.get("created"):
            proposal.status = "approved"
    elif proposal.action_type == "update":
        patch = dict(proposal.patch)
        if modifications:
            patch.update(modifications)
        result = engine.update_entity(
            sc, proposal.table, proposal.target_id, patch,
            persist=True,
            approved_by=approved_by,
            source_citations=proposal.source_citations,
        )
        if result.get("updated"):
            proposal.status = "approved"
    else:
        return {"error": "unknown_action_type", "action_type": proposal.action_type}

    return result


def reject_proposal(proposal_id: str) -> dict:
    """Reject a pending proposal."""
    proposal = pending_proposals.get(proposal_id)
    if not proposal:
        return {"error": "proposal_not_found", "proposal_id": proposal_id}
    if proposal.status != "pending":
        return {"error": "proposal_already_processed", "status": proposal.status}
    proposal.status = "rejected"
    return {"rejected": True, "proposal_id": proposal_id}


# --------------------------------------------------------------------------- #
# Persona -> Person ID resolution
# --------------------------------------------------------------------------- #

def resolve_persona_to_person(persona_id: str | None, sc: engine.Scenario) -> str:
    """Map an active persona to its person_id for audit logging."""
    if not persona_id:
        return "system"
    for p in sc.personas:
        if p.get("id") == persona_id:
            return p.get("person_id", persona_id)
    return persona_id
