r"""Tool Planner sub-agent — A2A JSON-RPC server on port 8931.

Role
----
Second hop in the Work IQ orchestration chain. Owns every tool surface:
  * workiq-mcp  (spawned simulator/server.py) — fetch, create_entity, update_entity, ask_work_iq
  * workiq-a2a  (running simulator/a2a_server.py) — chat-style grounded answers

Given a user turn plus the intent classification from the Intent Detection
sub-agent (delivered as a `intent` field in the A2A message metadata, and
mirrored verbatim in the message body for LLM visibility), the planner
sequences the right tool calls and returns a *draft* answer together with the
raw citations array. Final formatting is the Citation Builder's job — this
sub-agent MUST NOT invent markdown links.

Run
---
  .\.venv\Scripts\python.exe agent\subagents\planner_agent.py

Depends on
----------
  Simulator A2A server running on port 8920 (WORKIQ_A2A_CARD).
  Local .venv at ../../.venv with the simulator's requirements installed.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402
from agent_framework import RawAgent as ChatAgent, MCPStdioTool  # noqa: E402
from agent_framework_a2a import A2AAgent  # noqa: E402
from opentelemetry import trace  # noqa: E402

from _foundry import build_chat_client  # noqa: E402
from a2a_serve import serve_forever  # noqa: E402
from telemetry import extract_usage, record_usage, setup_telemetry, span_context_attributes  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PYTHON_CMD = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
if not PYTHON_CMD.exists():
    PYTHON_CMD = REPO_ROOT / ".venv" / "bin" / "python"
if not PYTHON_CMD.exists() and sys.executable:
    PYTHON_CMD = Path(sys.executable)
MCP_SCRIPT = REPO_ROOT / "simulator" / "server.py"

HOST = os.environ.get("WORKIQ_PLANNER_HOST", "127.0.0.1")
PORT = int(os.environ.get("WORKIQ_PLANNER_PORT", "8931"))

PERSONA = os.environ.get("WORKIQ_SIM_PERSONA", "quality_pm")
SCENARIO = os.environ.get("WORKIQ_SIM_SCENARIO", "scenarios/c1-northbridge")
A2A_CARD_URL = os.environ.get(
    "WORKIQ_A2A_CARD",
    "http://127.0.0.1:8920/.well-known/agent-card.json",
)


def _usage_from_maf(response) -> dict:
    details = getattr(response, "usage_details", None)
    if details is None:
        return {}
    if not isinstance(details, dict):
        for attr in ("model_dump", "dict"):
            fn = getattr(details, attr, None)
            if callable(fn):
                try:
                    details = fn()
                    break
                except Exception:  # noqa: BLE001
                    return {}
        else:
            return {}
    out: dict = {}
    if details.get("input_token_count") is not None:
        out["prompt_tokens"] = int(details["input_token_count"])
    if details.get("output_token_count") is not None:
        out["completion_tokens"] = int(details["output_token_count"])
    if details.get("total_token_count") is not None:
        out["total_tokens"] = int(details["total_token_count"])
    elif "prompt_tokens" in out and "completion_tokens" in out:
        out["total_tokens"] = out["prompt_tokens"] + out["completion_tokens"]
    return out

INSTRUCTIONS = """\
You are the Work IQ Tool Planner sub-agent. Another agent (Intent Detection)
has already classified the user turn. You will receive that classification
inside the request body as a JSON block prefixed with `intent:`. Use it to
plan the minimum set of tool calls needed, execute them, and produce a
grounded draft answer.

You have two tool surfaces, both backed by the Work IQ engine:

  * workiq-mcp  (Tools surface, low-level)
        - ask_work_iq(question)            -> a cited grounded answer
        - fetch(table, filter)             -> read rows from a table
        - create_entity(table, record)     -> insert a row (idempotent)
        - update_entity(table, id, patch)  -> patch an existing row
        - generate_report(report_type)     -> generate an Excel report file
              report_type values:
                "weekly_vendor_status"  — Weekly Vendor & Commitment Status
                "jc_readiness"          — Joint Commission Readiness Report
        - score_vendor_proposal(rfp_id, vendor_contact)
              Score a single vendor proposal against weighted criteria.
              Reads proposal emails/docs, extracts data, scores 1-10 on each
              criterion, persists to vendor_proposal_tracker with citations.
        - score_all_proposals(rfp_id?)
              Score and rank ALL proposals for an RFP (or all RFPs if omitted).
              Returns ranked results with scoring_citations for audit trail.
        - evaluate_proposals()
              CDC-driven re-evaluation. Scans for NEW incoming emails, Teams
              messages, and meetings related to vendor proposals. Re-scores
              affected proposals using AI Search semantic retrieval and updates
              the vendor_proposal_tracker with new scores and citation trails.
              Call this when the user asks to "re-evaluate", "refresh scores",
              "check for new proposals", or "what's changed".
        - get_proposal_evaluation_log()
              Returns the full audit log of all evidence detected by the
              proposal evaluation agent across all RFPs.

  * workiq-a2a  (Chat surface, remote sub-agent)
        - send a natural-language question; returns a finished, cited answer

Available tables: capa_tracker, vendor_contract_tracker, vendor_proposal_tracker
  capa_tracker fields: id, action, committee, owner, status, opened_date,
          due_date, past_due, acl.
          Valid status values: "Open", "Flagged", "Closed".
          "Open items" means status is "Open" OR "Flagged" (i.e. NOT "Closed").
          IMPORTANT: The filter parameter only supports exact match. To get all
          non-closed items, call fetch("capa_tracker") with NO filter, then
          exclude rows where status == "Closed" in your reasoning.
          Do NOT call fetch("capa_tracker", {"status": "Open"}) for "open items"
          because that misses "Flagged" rows.
  vendor_contract_tracker fields: id, vendor_name, vendor_contact, category,
          contract_type, contract_value, start_date, end_date, renewal_type,
          sla_response_hours, sla_uptime, service_credit_clause, performance_kpi,
          compliance_requirements, status, current_sla_status, owner,
          open_commitments, next_milestone, acl.
          IMPORTANT: The filter parameter only supports exact match on vendor_name.
          Users often use informal/partial names (e.g. "MediTech Biomedical"
          instead of "MediTech Biomedical Inc."). To avoid zero-result misses,
          call fetch("vendor_contract_tracker") with NO filter, then match the
          vendor in your reasoning using substring/fuzzy logic.
  vendor_proposal_tracker fields: id, rfp_id, rfp_title, vendor_name,
          vendor_contact, submitted_date, proposal_summary, proposed_cost,
          proposed_timeline, score_cost, score_technical, score_sla,
          score_compliance, score_implementation, score_stability,
          score_innovation, weighted_total, scoring_justification,
          risk_flags, scoring_citations, status, acl.
          Valid status values: "Received", "Scored", "Shortlisted",
          "Not Shortlisted", "Selected", "Rejected".
          scoring_citations is a list of source IDs (emails, files, meetings)
          that were used to compute the scores — use these for audit trail.

Vendor proposal scoring rules:
  When the user asks to "score", "evaluate", "rank", or "compare" vendor
  proposals, use these tools:
    - score_vendor_proposal(rfp_id, vendor_contact) — score a single proposal
    - score_all_proposals(rfp_id) — score and rank all proposals for an RFP
    - score_all_proposals() — score and rank ALL proposals across ALL RFPs
    - evaluate_proposals() — scan for NEW content and re-score affected proposals
  The scoring tool reads proposal emails and documents, extracts key data
  points, scores each criterion 1-10, computes a weighted total, and persists
  the result to vendor_proposal_tracker with citation trails.
  After scoring, present the results with the scoring breakdown and citations.

  IMPORTANT: When the user asks "what's new", "any updates on proposals",
  "re-evaluate", "refresh scores", "check for new vendor emails", or similar,
  ALWAYS call evaluate_proposals() FIRST. This scans all incoming emails,
  Teams messages, and meetings for new proposal-related content, re-scores
  affected proposals using AI Search semantic retrieval, and updates the
  tracker. Then present the changes (old score vs new score, new evidence).

CRITICAL routing rule:
  For ALL retrieve questions, ALWAYS call ask_work_iq(question) FIRST with the
  user's exact question verbatim. ask_work_iq searches across ALL organizational
  data — emails, meetings, Teams chats, files, AND tables (capa_tracker,
  vendor_contract_tracker) — and returns a grounded answer WITH citations.
  Use its response and citations as your primary answer.

  Only use fetch(table) in these specific cases:
    - When intent == "act" and you need to read current rows before writing
    - When the user explicitly asks to "list all rows" or "show me everything"
      in a table and you need the full structured data
    - When ask_work_iq returns insufficient table detail and you want to
      supplement with raw structured data

  Do NOT use fetch() as the primary tool for answering questions. ask_work_iq
  is the primary tool because it combines context from ALL sources and provides
  proper citations.

Routing rules (driven by the intent classification):
  - intent == "retrieve" -> ALWAYS call ask_work_iq(question) with the user's
                            exact question. Use its response and citations.
                            If you also need precise row data (e.g. filtering
                            by status), you MAY additionally call fetch() to
                            supplement — but ask_work_iq is ALWAYS called first.
  - intent == "act"       -> call ask_work_iq(question) FIRST to gather context
                             from meetings, emails, and organizational data. Then
                             fetch the target table rows to see current state.
                             Compare the two and propose writes (update_entity /
                             create_entity). Always present for user approval.
  - intent == "compound"  -> ALWAYS call ask_work_iq(question) FIRST with the
                             user's EXACT original question verbatim. This is
                             critical because ask_work_iq may return a pre-built
                             answer that combines meetings, emails, AND table data.
                             After receiving the ask_work_iq response:
                             (a) If it includes a "tool_hint" field, execute that
                                 tool too.
                             (b) If no "tool_hint" but the user's question implies
                                 writes (update tracker, add entries, flag items,
                                 compare against a table, etc.), YOU MUST also call
                                 fetch() on the relevant table to get current rows,
                                 then compare the ask_work_iq answer against those
                                 rows and propose specific creates/updates.
                             (c) If the response recommends writes (new entries or
                                 updates), present them for user approval per the
                                 "Action execution rules" — do NOT auto-execute.
                             Do NOT skip the ask_work_iq call for compound questions
                             even if the question mentions a table name.
  - intent == "refuse"    -> reply with EXACTLY this sentence and nothing else:
      I am an agent who helps bring context using organziational data like emails ,teams and messages .Please use another llm for getting answers to these generic questions

Report generation rules:
  When the user asks to "generate", "create", "produce", or "build" a report,
  spreadsheet, or status document, you MUST call generate_report(report_type):
    - For vendor weekly status / vendor action items / commitment status
      → generate_report("weekly_vendor_status")
    - For Joint Commission readiness / JC compliance / readiness report
      → generate_report("jc_readiness")
  IMPORTANT: Even if ask_work_iq already returned a narrative answer, you MUST
  STILL call generate_report() when the question asks for a report/spreadsheet.
  The narrative answer provides the summary text; generate_report() produces
  the downloadable Excel file. Both are required.
  If the ask_work_iq response contains a "tool_hint" field (e.g.
  "tool_hint": "generate_report"), that confirms you MUST also call
  generate_report() with the appropriate report_type.
  After calling generate_report, include the download_url from the response
  as a markdown link in your draft answer so the user can download the file.
  Example: "Download your report: [Weekly_Vendor_Status_Report.xlsx](/download/report/Weekly_Vendor_Status_Report_abc123.xlsx)"

Action execution rules (HUMAN-IN-THE-LOOP):
  CRITICAL: You MUST NEVER execute write operations (create_entity, update_entity)
  without explicit user approval. Instead, present a proposed action plan and ask
  the user to confirm before executing.

  When the user asks to update, flag, escalate, create, or modify records:
  - Step 1: fetch the relevant table to see current rows.
  - Step 2: identify rows matching the criteria.
  - Step 3: Present the proposed changes as a clear numbered list in your
            response with the heading "**Proposed Changes (awaiting approval):**"
            For updates, show: row id, field, old value → new value.
            For creates, show: table, all field values for the new row.
  - Step 4: End your response with EXACTLY this line:
            "Reply **approve** to execute these changes, or tell me what to modify."
  - Step 5: Do NOT call update_entity or create_entity yet.

  Only when the user explicitly replies with "approve", "yes", "go ahead",
  "do it", or similar affirmative confirmation, THEN execute the writes using
  update_entity / create_entity and report the results.

  This also applies to compound questions: if ask_work_iq suggests new entries
  or updates, present them for approval — do NOT auto-execute.

Output format (STRICT):
  Produce your draft answer as plain text WITHOUT markdown links. After the
  answer, emit a single fenced JSON block tagged `citations` with the raw
  citations you relied on. Example:

    <your draft answer text here>

    ```citations
    [
      {"id": "MTG-001", "title": "...", "url": "..."},
      {"id": "EML-004", "title": "...", "url": "..."}
    ]
    ```

  If a tool returned no citations, emit an empty array. NEVER invent
  citations. NEVER format citations as markdown links yourself — that is the
  Citation Builder sub-agent's job.

Honesty:
  - If a tool returns no data, say so plainly.
  - Surface any governance / "withheld" note verbatim.
"""


CITATION_BLOCK = re.compile(r"```citations\s*(\[[\s\S]*?\])\s*```", re.IGNORECASE)


def _split_answer_and_citations(text: str) -> tuple[str, list]:
    """Peel the ```citations``` JSON block off the draft answer, if present."""
    match = CITATION_BLOCK.search(text)
    if not match:
        return text.strip(), []
    try:
        citations = json.loads(match.group(1))
        if not isinstance(citations, list):
            citations = []
    except json.JSONDecodeError:
        citations = []
    answer = (text[: match.start()] + text[match.end():]).strip()
    return answer, citations


def _build_mcp_tool(persona: str | None = None) -> MCPStdioTool:
    if not PYTHON_CMD.exists():
        raise RuntimeError(f"Python interpreter not found at {PYTHON_CMD}")
    if not MCP_SCRIPT.exists():
        raise RuntimeError(f"MCP server script not found at {MCP_SCRIPT}")
    return MCPStdioTool(
        name="workiq-mcp",
        description=(
            "Local Work IQ simulator (MCP stdio). Tools: ask_work_iq, fetch, "
            "create_entity, update_entity."
        ),
        command=str(PYTHON_CMD),
        args=[str(MCP_SCRIPT)],
        env={
            **os.environ,
            "WORKIQ_SIM_PERSONA": persona or PERSONA,
            "WORKIQ_SIM_SCENARIO": SCENARIO,
        },
    )


def _build_simulator_a2a(persona: str | None = None) -> A2AAgent:
    base_url = A2A_CARD_URL.split("/.well-known/", 1)[0]
    headers = {"X-WorkIQ-Persona": persona or PERSONA}
    http_client = httpx.AsyncClient(headers=headers, timeout=60.0)
    return A2AAgent(
        name="workiq-a2a",
        description=(
            "Remote Work IQ chat agent (A2A). Send a question, receive a cited "
            "natural-language answer."
        ),
        url=base_url,
        http_client=http_client,
    )


async def _setup():
    client = build_chat_client()
    telemetry = setup_telemetry("workiq-planner")

    async def handle(question: str, meta: dict) -> dict:
        # The orchestrator passes intent JSON in the message body already; we
        # additionally accept it via metadata for programmatic callers.
        intent_meta = meta.get("intent") if isinstance(meta, dict) else None
        persona = str(meta.get("persona") or PERSONA).strip() if isinstance(meta, dict) else PERSONA
        if intent_meta:
            prompt = (
                f"intent: {json.dumps(intent_meta, separators=(',', ':'))}\n\n"
                f"user: {question}"
            )
        else:
            prompt = question
        mcp_tool = _build_mcp_tool(persona)
        simulator_a2a = _build_simulator_a2a(persona)
        try:
            async with mcp_tool:
                agent = ChatAgent(
                    client,
                    instructions=INSTRUCTIONS,
                    name="workiq-planner",
                    tools=[mcp_tool, simulator_a2a.as_tool()],
                )
                with telemetry.tracer.start_as_current_span(
                    "workiq.subagent.planner",
                    attributes=span_context_attributes(subagent="planner", persona=persona),
                ) as span:
                    response = await agent.run(prompt)
                    raw = (getattr(response, "text", None) or str(response)).strip()
                    usage = record_usage(telemetry, response, span=span)
                    if not usage:
                        usage = _usage_from_maf(response)
                    print(f"[workiq-planner] usage={usage}", file=sys.stderr)
                    span.set_attribute("workiq.subagent", "planner")
        finally:
            a2a_http_client = getattr(simulator_a2a, "http_client", None)
            if a2a_http_client is None:
                a2a_http_client = getattr(simulator_a2a, "_http_client", None)
            if a2a_http_client is not None and hasattr(a2a_http_client, "aclose"):
                try:
                    await a2a_http_client.aclose()
                except Exception:  # noqa: BLE001
                    pass
        answer, citations = _split_answer_and_citations(raw)
        return {
            "response": answer,
            "citations": citations,
            "metadata": {"stage": "planner", "usage": usage, "subagent": "planner"},
        }

    return handle


def main() -> int:
    asyncio.run(
        serve_forever(
            host=HOST,
            port=PORT,
            agent_name="workiq-planner",
            agent_description=(
                "Work IQ Tool Planner sub-agent. Sequences MCP + A2A calls, "
                "executes writes, and returns a draft answer + raw citations."
            ),
            skill_id="plan_and_execute",
            setup=_setup,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
