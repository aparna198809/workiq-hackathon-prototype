"""
Vendor Proposal Scoring Engine — LLM-driven extraction and scoring.

Reads proposal emails and documents from the scenario, extracts key data
points, scores them against a weighted evaluation matrix, and writes results
(with citation trails) into the vendor_proposal_tracker table.

Scoring criteria (weighted):
  Cost & TCO           20%
  Technical Capability 20%
  Performance & SLA    15%
  Compliance & Security15%
  Implementation Plan  10%
  Vendor Stability     10%
  Innovation & Roadmap 10%
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SIM_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SIM_DIR))

import engine  # noqa: E402
import search_client as _search  # noqa: E402

# Weights for scoring criteria (must sum to 1.0)
CRITERIA_WEIGHTS = {
    "score_cost": 0.20,
    "score_technical": 0.20,
    "score_sla": 0.15,
    "score_compliance": 0.15,
    "score_implementation": 0.10,
    "score_stability": 0.10,
    "score_innovation": 0.10,
}

SCORING_PROMPT = """\
You are a procurement evaluation analyst. Given a vendor proposal (email + document),
extract key data points and score the proposal on a 1-10 scale for each criterion.

EVALUATION CRITERIA (score each 1-10):
1. Cost & TCO (score_cost): Annual cost, total cost of ownership, hidden fees, value for money
2. Technical Capability (score_technical): Solution fit, integration readiness (esp. with LuminaEHR/ClearPoint), scalability
3. Performance & SLA (score_sla): Uptime guarantees, response times, service credits, support coverage
4. Compliance & Security (score_compliance): HIPAA, SOC 2, HITRUST, DEA, Joint Commission requirements
5. Implementation Plan (score_implementation): Timeline, resource commitment, training, go-live approach
6. Vendor Stability (score_stability): Years in market, client count, financial health, references
7. Innovation & Roadmap (score_innovation): Product roadmap, AI/automation, differentiating features

VENDOR PROPOSAL DATA:
{proposal_text}

RFP CONTEXT:
{rfp_context}

Respond with ONLY a JSON object (no markdown fencing, no explanation):
{{
  "vendor_name": "<vendor name>",
  "proposed_cost": "<annual cost and TCO>",
  "proposed_timeline": "<implementation timeline>",
  "proposal_summary": "<2-3 sentence summary of the proposal>",
  "score_cost": <1-10>,
  "score_technical": <1-10>,
  "score_sla": <1-10>,
  "score_compliance": <1-10>,
  "score_implementation": <1-10>,
  "score_stability": <1-10>,
  "score_innovation": <1-10>,
  "scoring_justification": "<paragraph explaining scores with evidence from the proposal>",
  "risk_flags": "<key risks identified, or 'None significant'>"
}}
"""

# RFP context descriptions for scoring
RFP_CONTEXT = {
    "RFP-001": (
        "Telehealth Platform for Northbridge Health Network. Budget: $150K-$250K/year. "
        "Requirements: video conferencing, EHR integration with LuminaEHR (HL7/FHIR), "
        "e-prescribing, HIPAA compliance, mobile app, 99.5%+ uptime. "
        "Existing EHR: LuminaEHR (deployed at Westgate clinic). "
        "Existing CPOE: ClearPoint Clinical Solutions."
    ),
    "RFP-002": (
        "Clinical Analytics & Reporting Platform. Budget: $100K-$180K/year. "
        "Requirements: real-time dashboards, population health management, "
        "12 Joint Commission report templates, predictive analytics, "
        "integration with LuminaEHR AND ClearPoint CPOE (both HL7/FHIR). "
        "Joint Commission review upcoming — all 12 report templates needed immediately."
    ),
    "RFP-003": (
        "Medical Waste Management service for all Northbridge facilities. "
        "Budget: $60K-$100K/year. Requirements: scheduled pickups, emergency collection, "
        "DOT-compliant transport, DEA-compliant pharmaceutical waste handling, "
        "manifesting/tracking portal, staff OSHA training."
    ),
}


def compute_weighted_total(scores: dict) -> float:
    """Compute weighted total from individual criterion scores."""
    total = 0.0
    for field, weight in CRITERIA_WEIGHTS.items():
        val = scores.get(field, 0)
        if isinstance(val, (int, float)):
            total += val * weight
    return round(total, 2)


def _gather_proposal_text(sc: engine.Scenario, rfp_id: str, vendor_contact: str) -> tuple[str, list[str]]:
    """Gather all email and document text for a proposal, returning (text, citation_ids).

    Uses a two-pass approach:
      1. AI Search (semantic + keyword hybrid) to find relevant content
      2. Direct fixture scan as fallback/supplement for the vendor's own emails
    """
    texts = []
    citations = []

    # Resolve vendor name
    person_entry = sc.index.get(vendor_contact)
    vendor_name = ""
    if person_entry:
        _, person = person_entry
        dept = person.get("department", "")
        if "Vendor" in dept:
            vendor_name = dept.replace("Vendor (", "").rstrip(")")

    # --- Pass 1: AI Search (semantic hybrid) ---
    if _search.is_available() and vendor_name:
        query = f"{vendor_name} {rfp_id} proposal cost SLA compliance implementation"
        query_embedding = _search.get_embeddings_batch([query])
        query_vec = query_embedding[0] if query_embedding is not None else None

        search_results = _search.search(
            query_embedding=query_vec,
            question=query,
            persona_id=None,  # agent sees all for scoring
            scenario_name=sc.root.name,
            k=15,
        )

        for hit in search_results:
            hit_id = hit["id"]
            if hit_id not in citations:
                texts.append(f"[{hit['kind'].title()} {hit_id}] {hit.get('title', '')}\n{hit['text']}")
                citations.append(hit_id)
                print(f"[scoring] AI Search hit: {hit_id} ({hit['kind']}, score={hit['score']:.2f})",
                      file=sys.stderr)

    # --- Pass 2: direct fixture scan for vendor's own emails + attachments ---
    for email in sc.emails:
        if email.get("from") == vendor_contact and email["id"] not in citations:
            body = email.get("body", "")
            subject = email.get("subject", "")
            searchable = (subject + " " + body).lower().replace("-", "")
            rfp_norm = rfp_id.lower().replace("-", "")
            if rfp_norm in searchable or \
               any(rfp_norm in (a if isinstance(a, str) else "").lower().replace("-", "") for a in email.get("attachments", [])):
                texts.append(f"[Email {email['id']}] Subject: {subject}\n{body}")
                citations.append(email["id"])

        # Attachments from vendor emails
        if email.get("from") == vendor_contact:
            for att_id in email.get("attachments", []):
                if isinstance(att_id, str) and att_id not in citations:
                    entry = sc.index.get(att_id)
                    if entry:
                        _, record = entry
                        summary = record.get("summary", "")
                        excerpt = record.get("content_excerpt", "")
                        texts.append(f"[Document {att_id}] {record.get('name', '')}\n{summary}\n{excerpt}")
                        citations.append(att_id)

    # --- Pass 3: keyword fallback for internal references ---
    if vendor_name:
        for email in sc.emails:
            if email.get("from") != vendor_contact and email["id"] not in citations:
                body = email.get("body", "")
                if vendor_name.lower() in body.lower():
                    texts.append(f"[Internal Email {email['id']}] {email.get('subject', '')}\n{body}")
                    citations.append(email["id"])

        for msg in sc.teams_messages:
            if msg["id"] not in citations:
                msg_text = msg.get("text", "")
                if vendor_name.lower() in msg_text.lower():
                    texts.append(f"[Teams {msg['id']}] {msg.get('channel', '')}: {msg_text}")
                    citations.append(msg["id"])

        for mtg in sc.meetings:
            if mtg["id"] not in citations:
                recap = mtg.get("recap", "")
                if vendor_name.lower() in recap.lower():
                    texts.append(f"[Meeting {mtg['id']}] {mtg.get('title', '')}\n{recap}")
                    citations.append(mtg["id"])

    return "\n\n---\n\n".join(texts), citations


def _find_proposals_for_rfp(sc: engine.Scenario, rfp_id: str) -> list[dict]:
    """Find proposal emails for a given RFP by matching thread IDs and subjects."""
    proposals = []
    rfp_thread_map = {
        "RFP-001": "THR-RFP-TELEHEALTH",
        "RFP-002": "THR-RFP-ANALYTICS",
        "RFP-003": "THR-RFP-WASTE",
    }
    thread_id = rfp_thread_map.get(rfp_id, "")

    for email in sc.emails:
        if email.get("thread_id") == thread_id and email.get("from", "").startswith("PPL-"):
            # External vendor emails (not from internal PPL-015 Marcus Webb)
            sender = email["from"]
            person = sc.index.get(sender)
            if person:
                _, p = person
                dept = p.get("department", "")
                if "Vendor" in dept:
                    proposals.append({
                        "email": email,
                        "vendor_contact": sender,
                        "rfp_id": rfp_id,
                    })

    return proposals


def score_proposal_with_llm(
    proposal_text: str,
    rfp_id: str,
    citations: list[str],
) -> dict | None:
    """Use the LLM to extract data and score a proposal. Returns scores dict or None."""
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
    if not endpoint:
        return None

    import httpx
    from azure.identity import AzureCliCredential

    base = re.sub(r"/openai/v1$", "", endpoint)
    deploy = os.environ.get("AZURE_AI_FOUNDRY_DEPLOYMENT", "gpt-4o-mini")
    api_version = "2024-02-01"
    url = f"{base}/openai/deployments/{deploy}/chat/completions?api-version={api_version}"

    rfp_context = RFP_CONTEXT.get(rfp_id, "")
    prompt = SCORING_PROMPT.format(proposal_text=proposal_text, rfp_context=rfp_context)

    try:
        cred = AzureCliCredential()
        token = cred.get_token("https://cognitiveservices.azure.com/.default").token
        resp = httpx.post(
            url,
            json={
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 1000,
            },
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=60.0,
        )
        if resp.status_code != 200:
            print(f"[scoring] LLM call failed ({resp.status_code}): {resp.text[:200]}", file=sys.stderr)
            return None

        content = resp.json()["choices"][0]["message"]["content"].strip()
        # Strip markdown fencing if present
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
        scores = json.loads(content)

        # Compute weighted total
        scores["weighted_total"] = compute_weighted_total(scores)
        scores["scoring_citations"] = citations

        return scores

    except Exception as exc:
        print(f"[scoring] LLM scoring error: {exc}", file=sys.stderr)
        return None


def score_proposal_rule_based(
    proposal_text: str,
    rfp_id: str,
    citations: list[str],
) -> dict:
    """Rule-based scoring fallback when no LLM is available."""
    text_lower = proposal_text.lower()

    # Cost scoring
    cost_score = 5
    cost_matches = re.findall(r"\$[\d,]+(?:,\d{3})*(?:\.\d+)?(?:k|K)?", proposal_text)
    annual_costs = []
    for m in cost_matches:
        val = m.replace("$", "").replace(",", "")
        if val.endswith(("k", "K")):
            val = float(val[:-1]) * 1000
        else:
            val = float(val)
        if 50000 <= val <= 500000:
            annual_costs.append(val)
    if annual_costs:
        lowest = min(annual_costs)
        if lowest < 100000:
            cost_score = 9
        elif lowest < 150000:
            cost_score = 7
        elif lowest < 200000:
            cost_score = 6
        else:
            cost_score = 5

    # Technical scoring
    tech_score = 5
    tech_keywords = ["luminaehr", "hl7", "fhir", "pre-built", "native connector", "clearpoint"]
    tech_hits = sum(1 for k in tech_keywords if k in text_lower)
    tech_score = min(10, 5 + tech_hits)

    # SLA scoring
    sla_score = 5
    if "99.95%" in text_lower:
        sla_score = 10
    elif "99.9%" in text_lower:
        sla_score = 8
    elif "99.5%" in text_lower:
        sla_score = 5
    if "1-hour" in text_lower or "1h p1" in text_lower:
        sla_score = min(10, sla_score + 2)
    elif "2-hour" in text_lower or "2h p1" in text_lower:
        sla_score = min(10, sla_score + 1)

    # Compliance scoring
    comp_score = 5
    comp_keywords = ["hitrust", "soc 2 type ii", "soc 2", "hipaa", "dea", "epcs", "fda"]
    comp_hits = sum(1 for k in comp_keywords if k in text_lower)
    comp_score = min(10, 4 + comp_hits * 2)
    if "in progress" in text_lower and "soc 2" in text_lower:
        comp_score = max(3, comp_score - 3)

    # Implementation scoring
    impl_score = 5
    week_matches = re.findall(r"(\d+)\s*(?:-\s*\d+\s*)?week", text_lower)
    if week_matches:
        weeks = int(week_matches[0])
        if weeks <= 6:
            impl_score = 8
        elif weeks <= 8:
            impl_score = 7
        elif weeks <= 10:
            impl_score = 6
        else:
            impl_score = 5

    # Stability scoring
    stab_score = 5
    client_matches = re.findall(r"(\d+)\+?\s*(?:healthcare\s+)?clients", text_lower)
    if client_matches:
        clients = int(client_matches[0])
        if clients >= 500:
            stab_score = 9
        elif clients >= 200:
            stab_score = 8
        elif clients >= 100:
            stab_score = 7
        elif clients >= 50:
            stab_score = 6
        elif clients < 50:
            stab_score = 4
    year_matches = re.findall(r"(\d+)\s*years?\s*(?:of\s+)?(?:experience|in\s+(?:healthcare|market))", text_lower)
    if year_matches:
        years = int(year_matches[0])
        if years >= 10:
            stab_score = min(10, stab_score + 1)
    if "founded 2023" in text_lower or "startup" in text_lower:
        stab_score = max(3, stab_score - 2)

    # Innovation scoring
    innov_score = 5
    innov_keywords = ["ai-powered", "artificial intelligence", "machine learning",
                      "predictive", "automated", "sentiment analysis", "zero-landfill",
                      "carbon-neutral", "sustainability"]
    innov_hits = sum(1 for k in innov_keywords if k in text_lower)
    innov_score = min(10, 5 + innov_hits * 2)

    scores = {
        "score_cost": cost_score,
        "score_technical": tech_score,
        "score_sla": sla_score,
        "score_compliance": comp_score,
        "score_implementation": impl_score,
        "score_stability": stab_score,
        "score_innovation": innov_score,
    }
    scores["weighted_total"] = compute_weighted_total(scores)
    scores["scoring_citations"] = citations

    # Generate basic justification
    scores["scoring_justification"] = (
        f"Rule-based scoring: Cost={cost_score}/10, Technical={tech_score}/10, "
        f"SLA={sla_score}/10, Compliance={comp_score}/10, Implementation={impl_score}/10, "
        f"Stability={stab_score}/10, Innovation={innov_score}/10. "
        f"Weighted total: {scores['weighted_total']}."
    )

    # Extract proposal summary and cost from text
    cost_str = annual_costs[0] if annual_costs else "Not specified"
    if isinstance(cost_str, float):
        cost_str = f"${cost_str:,.0f}/year"
    scores["proposed_cost"] = cost_str

    week_str = f"{week_matches[0]} weeks" if week_matches else "Not specified"
    scores["proposed_timeline"] = week_str

    scores["risk_flags"] = []
    if comp_score < 6:
        scores["risk_flags"].append("Compliance gaps detected")
    if stab_score < 6:
        scores["risk_flags"].append("Vendor stability concern")
    if tech_score < 6:
        scores["risk_flags"].append("Integration risk")
    scores["risk_flags"] = "; ".join(scores["risk_flags"]) if scores["risk_flags"] else "None significant"

    return scores


def score_single_proposal(
    sc: engine.Scenario,
    rfp_id: str,
    vendor_contact: str,
    persona_id: str | None = None,
) -> dict:
    """Score a single vendor proposal. Returns the scored tracker row with citations."""
    proposal_text, citations = _gather_proposal_text(sc, rfp_id, vendor_contact)
    if not proposal_text:
        return {"error": f"No proposal found for vendor {vendor_contact} on {rfp_id}"}

    # Try LLM scoring first, fall back to rule-based
    scores = score_proposal_with_llm(proposal_text, rfp_id, citations)
    scoring_method = "llm"
    if scores is None:
        scores = score_proposal_rule_based(proposal_text, rfp_id, citations)
        scoring_method = "rule_based"

    # Look up vendor name
    person_entry = sc.index.get(vendor_contact)
    vendor_name = "Unknown"
    if person_entry:
        _, person = person_entry
        dept = person.get("department", "")
        vendor_name = dept.replace("Vendor (", "").rstrip(")") if "Vendor" in dept else person.get("name", "Unknown")

    # Build tracker row
    now = datetime.now(timezone.utc)
    existing_rows = sc.tables.get("vendor_proposal_tracker", [])
    proposal_id = f"PROP-{len(existing_rows) + 1:03d}"

    # Check if this vendor already has a scored proposal for this RFP
    for row in existing_rows:
        if row.get("rfp_id") == rfp_id and row.get("vendor_contact") == vendor_contact:
            proposal_id = row["id"]
            break

    tracker_row = {
        "id": proposal_id,
        "rfp_id": rfp_id,
        "rfp_title": RFP_CONTEXT.get(rfp_id, rfp_id).split(".")[0],
        "vendor_name": scores.get("vendor_name", vendor_name),
        "vendor_contact": vendor_contact,
        "submitted_date": now.strftime("%Y-%m-%d"),
        "proposal_summary": scores.get("proposal_summary", ""),
        "proposed_cost": scores.get("proposed_cost", ""),
        "proposed_timeline": scores.get("proposed_timeline", ""),
        "score_cost": scores["score_cost"],
        "score_technical": scores["score_technical"],
        "score_sla": scores["score_sla"],
        "score_compliance": scores["score_compliance"],
        "score_implementation": scores["score_implementation"],
        "score_stability": scores["score_stability"],
        "score_innovation": scores["score_innovation"],
        "weighted_total": scores["weighted_total"],
        "scoring_justification": scores.get("scoring_justification", ""),
        "risk_flags": scores.get("risk_flags", ""),
        "scoring_method": scoring_method,
        "scoring_citations": scores.get("scoring_citations", citations),
        "scored_at": now.isoformat(timespec="seconds"),
        "scored_by": persona_id or "agent",
        "status": "Scored",
        "acl": ["ops_director", "procurement_eval", "vendor_manager", "quality_pm"],
    }

    return tracker_row


def score_all_proposals_for_rfp(
    sc: engine.Scenario,
    rfp_id: str,
    persona_id: str | None = None,
    persist: bool = False,
) -> list[dict]:
    """Score all proposals for a given RFP. Returns scored rows sorted by weighted_total."""
    proposals = _find_proposals_for_rfp(sc, rfp_id)
    if not proposals:
        return []

    scored = []
    for prop in proposals:
        result = score_single_proposal(sc, rfp_id, prop["vendor_contact"], persona_id)
        if "error" not in result:
            scored.append(result)

    # Sort by weighted total descending
    scored.sort(key=lambda r: r.get("weighted_total", 0), reverse=True)

    # Assign rank
    for i, row in enumerate(scored):
        row["rank"] = i + 1

    if persist:
        _persist_scores(sc, scored)

    return scored


def score_all_rfps(
    sc: engine.Scenario,
    persona_id: str | None = None,
    persist: bool = False,
) -> dict[str, list[dict]]:
    """Score all proposals across all RFPs. Returns {rfp_id: [scored_rows]}."""
    results = {}
    for rfp_id in RFP_CONTEXT:
        scored = score_all_proposals_for_rfp(sc, rfp_id, persona_id, persist=False)
        if scored:
            results[rfp_id] = scored

    if persist and results:
        all_rows = []
        for rows in results.values():
            all_rows.extend(rows)
        _persist_scores(sc, all_rows)

    return results


def _persist_scores(sc: engine.Scenario, scored_rows: list[dict]):
    """Write scored rows into the vendor_proposal_tracker table."""
    table_name = "vendor_proposal_tracker"
    existing = sc.tables.get(table_name, [])

    for new_row in scored_rows:
        # Update existing or append
        found = False
        for i, existing_row in enumerate(existing):
            if existing_row.get("rfp_id") == new_row["rfp_id"] and \
               existing_row.get("vendor_contact") == new_row["vendor_contact"]:
                new_row["id"] = existing_row["id"]
                existing[i] = new_row
                sc.index[new_row["id"]] = ("vendor_proposal", new_row)
                found = True
                break
        if not found:
            existing.append(new_row)
            sc.index[new_row["id"]] = ("vendor_proposal", new_row)

    sc.tables[table_name] = existing
    engine._persist_table(sc, table_name)
    print(f"[scoring] Persisted {len(scored_rows)} scored proposals to {table_name}", file=sys.stderr)
