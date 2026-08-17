# Work IQ — Demo Preparation Guide
## 20-Minute Management Presentation Reference

**Prepared by:** Somolina Saha  
**Date:** 24-JUL-2026  
**Solution:** Work IQ — AI-Powered Vendor & Compliance Intelligence Agent  
**Platform:** Microsoft Agent Framework + Azure AI Foundry + M365 Work IQ (MCP & A2A)

---

## Table of Contents

1. [Demo Flow & Timing](#1-demo-flow--timing)
2. [Opening — The Problem (2 min)](#2-opening--the-problem-2-min)
3. [Single-Signal Questions (4 min)](#3-single-signal-questions-4-min)
4. [Multi-Signal Questions (5 min)](#4-multi-signal-questions-5-min)
5. [Agentic Synthesis — The Differentiator (4 min)](#5-agentic-synthesis--the-differentiator-4-min)
6. [Write-Back Actions & Automated Reports (3 min)](#6-write-back-actions--automated-reports-3-min)
7. [Governance, Guardrails & Agent Architecture (3 min)](#7-governance-guardrails--agent-architecture-3-min)
8. [Value Proposition — Why Not Just M365 Copilot? (2 min)](#8-value-proposition--why-not-just-m365-copilot-2-min)
9. [Pre-Demo Checklist](#9-pre-demo-checklist)
10. [Appendix — Full Citation Reference](#10-appendix--full-citation-reference)

---

## 1. Demo Flow & Timing

| Segment | Duration | What to Show |
|---------|----------|--------------|
| The Problem | 2 min | Pain point narrative — manual reconstruction, missed SLA windows |
| Single-Signal Retrieval | 4 min | 2 questions — grounded answers from one source with citations |
| Multi-Signal Correlation | 5 min | 2 questions — cross-referencing emails + meetings + Teams |
| Agentic Synthesis + RBAC | 4 min | 1 question with persona switching to show governance |
| Write-Back & Reports | 3 min | Update tracker + generate Excel report on demand |
| Architecture & Guardrails | 3 min | Agent pipeline, guardrails, scope refusal, telemetry |
| Value vs. Copilot | 2 min | Differentiation table, quantified ROI |

**Total: ~23 minutes** (leaves buffer for Q&A within a 30-min slot, or tight for 20 min — skip one single-signal question if needed)

---

## 2. Opening — The Problem (2 min)

### Talking Points

> "Vendor commitments, SLA obligations, and regulatory compliance data are fragmented across Microsoft 365 — buried in emails, meeting recaps, Teams channels, SharePoint files, and internal trackers."

**Key stats to mention:**
- Operations teams spend **4–8 hours per month** manually reconstructing vendor status for leadership reviews
- By the time a breach is identified, commercial leverage windows (penalty clauses, service credits) have often **expired**
- Joint Commission readiness reports require **1–2 days** of manual cross-referencing across committees

### The Hook (use this example)

> "In our demo scenario, Northbridge Health Network's MSA clause 7.4 entitles them to an 8% service credit per week if Lumina's go-live slips — but this intelligence lives in a **single confidential email between two executives**. Without proactive monitoring, leadership misses the activation window entirely. Our agent finds it, cross-references it, and alerts leadership with days of lead time."

---

## 3. Single-Signal Questions (4 min)

These prove **grounding fidelity** — the agent retrieves accurately from one M365 source with verifiable citations. No hallucination.

---

### Question S1: Quality Committee Decision

**Ask the agent:**
> "What did the quality steering committee decide about the medication-reconciliation policy in its last meeting, and who owns the follow-up?"

**Expected answer highlights:**
- Quality Steering Committee (10-JUN) decided to adopt the revised medication-reconciliation policy
- Requires documented reconciliation at every transition of care (admission, transfer, discharge)
- Replaces prior admission-only standard
- Follow-up owners: Angela Foster (policy document, CAPA-001), David Munoz (workflow + training), Priya Raman (compliance review)

**Citations:** `MTG-001` (Quality Steering Committee Meeting — 10-JUN)

**Demo talking point:** _"One question, one cited source. The agent didn't hallucinate the owner names or the policy details — every fact comes from MTG-001. This is grounding fidelity."_

---

### Question S2: MediTech Contract Status

**Ask the agent:**
> "What is the current status of the MediTech Biomedical contract and what are the open commitments?"

**Expected answer highlights:**
- $340K Preventive Maintenance & Calibration MSA — SLA status: Green
- Two open commitments: Westgate patient-monitor calibration (14-JUL) and autoclave validation (18-JUL)
- Joint Commission critical-path items
- Calibration certificates due within 48h (by 20-JUL)
- MSA auto-renews 01-SEP — team recommends renewal with tighter 24h SLA
- Service credit clause: 10% of monthly fee per month of breach

**Citations:** `VND-002` (vendor contract tracker), `EML-007`, `EML-008` (email thread with MediTech), `FILE-006` (MediTech MSA — restricted)

**Demo talking point:** _"The agent pulled from the vendor contract tracker AND the email thread AND the MSA document — all from a single question. Notice FILE-006 is restricted — if a non-authorized persona asks, they won't see the MSA terms."_

---

## 4. Multi-Signal Questions (5 min)

These prove **cross-signal correlation** — the agent stitches together 2+ source types into one coherent answer. This is what humans spend hours doing manually.

---

### Question M1: EHR Rollout Status (Emails + Teams + Meetings)

**Ask the agent:**
> "What is the current status of the EHR rollout at Westgate — combine the program channel updates with the last steering-committee meeting?"

**Expected answer highlights:**
- LuminaEHR build is configured, end-user training ~80% complete (trainers booked through 20-JUN)
- Single go-live blocker: medication-list data migration validation (Greg Sullivan, due 13-JUN) — 90% validated, on track
- Target go-live: 22-JUN, pending Lumina's written confirmation
- Robert Klein owns obtaining that confirmation

**Citations:** `MSG-001` (Teams channel), `MSG-002` (Teams channel), `MTG-004` (Steering Committee meeting)

**Demo talking point:** _"Three different sources — two Teams messages and a meeting — correlated into one rollout status. Previously, someone would have to open Teams, read the channel, then check the meeting minutes, then manually piece together the status. This took hours. The agent does it in seconds."_

---

### Question M2: Stalled Corrective Actions (Meetings + Emails + Tracker)

**Ask the agent:**
> "Which corrective actions from the last two quality meetings are still open, and what do the email threads say about why they're stalled?"

**Expected answer highlights:**
- Two open + past-due CAPAs from the 27-MAY and 10-JUN meetings:
  - **CAPA-001**: Medication-reconciliation policy — Angela Foster — due 09-JUN — PAST DUE. Stalled because she has the draft but is waiting on David Munoz's workflow steps.
  - **CAPA-004**: Westgate environment-of-care docs — Priya Raman — due 06-JUN — PAST DUE. Blocked waiting on a facilities vendor quote for signage.
- Both are on the Joint Commission readiness-review critical path.

**Citations:** `MTG-001` (Quality meeting 10-JUN), `MTG-002` (Quality meeting 27-MAY), `EML-005` (Angela Foster's email thread), `CAPA-001`, `CAPA-004` (tracker rows)

**Demo talking point:** _"This is the killer feature. The agent correlated meeting decisions with email explanations with tracker data. It didn't just say 'CAPA-001 is open' — it told you WHY it's stalled, pulling from Angela's email. No human would have connected those dots without 30 minutes of manual work."_

---

### Question M3: Vendor Contract Renewals (Emails + Tracker + Meeting)

**Ask the agent:**
> "Which vendor contracts are coming up for renewal and what actions has procurement recommended?"

**Expected answer highlights:**
- Three renewals on Q3-Q4 horizon:
  1. **MediTech** — 01-SEP-2026 (auto-renewal, notice window already open since 03-JUL). Recommendation: renew with tighter 24h SLA.
  2. **PharmaLink** — 15-OCT-2026 (90-day rebid notice). Recommendation: rebid the controlled-substance segment due to delivery delays.
  3. **ClearPoint** — 01-MAR-2027 (120-day notice). Flag v4.2 upgrade performance data for negotiation.
- Lumina also fixed-term ending 01-MAR-2027 — no immediate action.

**Citations:** `EML-014` (contract renewal calendar — restricted), `MSG-008` (Teams), `VND-002`, `VND-003`, `VND-004` (tracker), `MTG-005` (Vendor Performance Review)

**Demo talking point:** _"Notice how procurement's commercial recommendations come from a restricted email (EML-014). If a vendor liaison asks this question, they won't see the internal procurement strategy. That's governance in action."_

---

## 5. Agentic Synthesis — The Differentiator (4 min)

This is Tier 3 — the agent pulls from **4+ distinct sources across multiple committees**, applies RBAC, and delivers a comprehensive briefing.

---

### Question A1: Joint Commission Readiness Prep

**Ask as `ops_director` persona:**
> "Prep me for the Joint Commission readiness review: what did the quality committee decide on med-reconciliation, who owns the corrective action, did credentialing close the related onboarding gap, and what's outstanding?"

**Expected answer (full — ops_director sees everything):**
1. **Quality decision**: Adopted revised medication-reconciliation policy (10-JUN). CAPA-001 tracks it — Angela Foster (policy), David Munoz (workflow), Priya Raman (compliance).
2. **Credentialing closure**: Yes — provider-onboarding gap closed 05-JUN (CAPA-002 Closed, Sandra Okafor). A separate HR-sensitive matter (CAPA-005) handled in closed session.
3. **Outstanding**: CAPA-001 (past due) and CAPA-004 (past due) — both must close before the review.

**Citations:** `MTG-001`, `MTG-003`, `EML-006`, `FILE-004`, `CAPA-001`, `CAPA-002`, `FILE-003`

---

### RBAC Demo — Switch persona to `quality_pm`:

**Ask the same question as `quality_pm`:**

**Expected answer (redacted):**
- Same content EXCEPT: "An HR-sensitive credentialing personnel file is withheld" — the agent fail-closes with an explicit governance note.
- `FILE-003` (restricted citation) is NOT shown.

**Demo talking point:** _"Same question, different persona, different answer. The quality PM doesn't see the HR-sensitive credentialing file. And critically — the agent doesn't silently omit it. It explicitly tells you something was withheld. That's fail-closed governance. M365 Copilot doesn't do this."_

### RBAC Summary Table (show on slide)

| Persona | Sees | Withheld |
|---------|------|----------|
| **Operations Director** | Full portfolio including commercial penalty clauses | Nothing |
| **Vendor Manager** | All vendor contracts, SLAs, commercial terms | HR credentialing personnel files |
| **Quality PM** | Quality + credentialing decisions, CAPA tracker | HR personnel file |
| **Credentialing Lead** | Full credentialing including HR-sensitive data | Commercial penalty threads |
| **Vendor Liaison (External)** | Only vendor-facing rollout signals | Internal strategy, commercial terms, HR data |

---

## 6. Write-Back Actions & Automated Reports (3 min)

### Question W1: Update Tracker (MCP Tools — Write-Back)

**Ask the agent:**
> "For every open corrective action from the quality committee, update its status in our program tracker and flag the ones past due."

**Expected behavior:**
- Agent identifies CAPA-001 and CAPA-004 as open + past due
- Calls `update_entity("capa_tracker", "CAPA-001", {"status": "Escalated", "past_due": true})`
- Calls `update_entity("capa_tracker", "CAPA-004", {"status": "Escalated", "past_due": true})`
- Reports the changes made with citations

**Citations:** `MTG-001`, `MTG-002`, `CAPA-001`, `CAPA-004`

**Demo talking point:** _"The agent didn't just tell us what to do — it actually executed the update. It called the MCP update_entity tool twice and changed the tracker. This is an operational agent, not just a Q&A chatbot."_

---

### Question W2: Generate Weekly Report (Automated Excel)

**Ask the agent:**
> "Generate the weekly vendor and commitment status report across all active vendor contracts."

**Expected behavior:**
- Agent calls `generate_report("weekly_vendor_status")`
- Produces a multi-sheet Excel workbook with:
  - **Sheet 1:** Vendor Dashboard (4 vendors, $2.34M portfolio)
  - **Sheet 2:** SLA Status (Green/Amber/Red per vendor)
  - **Sheet 3:** Open Commitments (5 across 4 vendors)
  - **Sheet 4:** Renewal Horizon (3 upcoming renewals)
  - **Sheet 5:** Risk Flags (PharmaLink amber, clause 5.2 in play)
- Returns download link

**Citations:** `VND-001`, `VND-002`, `VND-003`, `VND-004`, `EML-013`, `MSG-006`, `MTG-005`

**Proactive alert (included in report):**
> "PharmaLink's controlled-substance delivery is 5 days late — SLA clause 5.2 (5% credit/week) activates in 2 days if not resolved."

**Demo talking point:** _"On-demand, leadership-ready Excel report. No manual data gathering. The agent pulled live data from emails, meetings, Teams, and the vendor tracker — and produced a downloadable spreadsheet in seconds. This replaces a 4–8 hour monthly exercise."_

---

## 7. Governance, Guardrails & Agent Architecture (3 min)

### Agent Architecture — Deterministic Three-Hop Pipeline

```
User Question
    │
    ▼
┌────────────────────────┐
│   1. Intent Detector    │   Classifies: retrieve | act | compound | refuse
│      (Port 8930)        │   No tools — pure classifier, fast + cheap
│      GPT-4o-mini        │   Guardrail: refuses out-of-scope questions
└──────────┬─────────────┘
           │
           ▼
┌────────────────────────┐
│   2. Tool Planner       │   Executes MCP tool calls against M365 data
│      (Port 8931)        │   Tools: ask_work_iq, fetch, create/update_entity,
│      GPT-4o-mini        │          generate_report
│      + MCP + A2A        │   Owns both tool surfaces (MCP for data, A2A for synthesis)
└──────────┬─────────────┘
           │
           ▼
┌────────────────────────┐
│   3. Citation Builder   │   Formats sources as verifiable [Title](url) links
│      (Port 8932)        │   No tools — deterministic formatting only
│      GPT-4o-mini        │   Never invents claims or citations
└──────────┬─────────────┘
           │
           ▼
   Final Answer + Citations + Governance Notes
```

### Why This Architecture Matters

| Design Decision | Why |
|----------------|-----|
| **Three independent sub-agents** | Separation of concerns — intent classification doesn't need tool access; citation formatting doesn't need data access |
| **Deterministic pipeline** | Every question follows the same 3-hop path — auditable, reproducible, debuggable |
| **A2A (Agent-to-Agent) transport** | Sub-agents communicate via JSON-RPC 2.0 — industry-standard, testable, replaceable |
| **MCP (Model Context Protocol)** | Tool calls to the data layer use the same protocol as real Work IQ — agent code doesn't change when you swap simulator for production |
| **OpenTelemetry tracing** | Per-subagent token usage, latency metrics, full execution trails |

---

### Guardrails & Governance

#### 1. Scope Guardrail (Intent Detection)

The Intent Detector classifies every question. If it's clearly out-of-scope (general knowledge, coding, math, trivia), the agent **refuses** with an exact sentence:

> _"I am an agent who helps bring context using organizational data like emails, teams and messages. Please use another LLM for getting answers to these generic questions."_

**Demo it:** Ask _"What is the capital of France?"_ — the agent refuses cleanly.

#### 2. Role-Based Access Control (RBAC)

- Every data fixture (email, meeting, file, tracker row) carries an `acl` field — a list of authorized persona IDs
- The engine filters citations **server-side** before the LLM sees them
- When any citation is restricted, the system **fail-closes**: returns a redacted answer with an explicit governance note
- **Never silently omits data** — the user always knows something was withheld

#### 3. Citation Verifiability

- Every fact in the answer is traced back to a specific source ID (e.g., `EML-001`, `MTG-004`, `VND-002`)
- The Citation Builder sub-agent renders these as clickable markdown links
- The agent is instructed: _"Never invent facts. If a tool returns no citations, say so."_

#### 4. Deterministic Refusal

- The refusal sentence is hardcoded — the agent cannot be prompted to answer generic questions
- No "helpful override" — the scope guardrail is strict and non-negotiable

#### 5. CDC Reconciliation & Approval Workflow

- Change Data Capture detects new action items from meetings/Teams
- Reconciliation agent matches them against existing CAPA tracker entries using text similarity
- Proposals (create or update) require **human approval** before execution
- Full audit trail: `created_by`, `modified_by`, `approval_log` stamped on every change
- No autonomous writes without human-in-the-loop approval

#### 6. Telemetry & Observability

- Full **OpenTelemetry** tracing across all 3 sub-agents
- Per-subagent metrics: token usage (prompt + completion), latency, request count, failure count
- Execution trail visible in the web UI — users can see exactly which tools were called
- Production path: Azure Monitor / Application Insights integration scaffolded

#### 7. Token Budget & Rate Limiting (Web UI)

- Configurable per-session token limits (`WORKIQ_WEB_TOKEN_LIMIT`)
- Cooldown period between requests (`WORKIQ_WEB_COOLDOWN_SECONDS`)
- Client-side cooldown timer shown in the UI

---

### AI Search — How It Adds Value

| Capability | How AI Search Powers It |
|-----------|------------------------|
| **Hybrid search** | Keyword + vector search across all organizational content — emails, meetings, files, Teams messages |
| **Server-side ACL filtering** | OData `$filter` on the `acl` collection field — governance enforced before results reach the LLM |
| **Document cracking** | Built-in PDF text extraction and OCR for attachments (MSAs, SLA documents, policy files) |
| **Embedding-based matching** | Vector similarity for natural-language questions that don't use exact keywords |
| **Content-source tagging** | `content_source` field distinguishes direct text from attachment-extracted content |
| **Scenario-scoped indexing** | Each scenario is indexed separately — no cross-contamination between tenants |

**Production path:** Swap the simulator's in-memory engine for Azure AI Search with a blob indexer pointing at SharePoint/OneDrive — same index schema, same ACL filtering, production scale.

---

## 8. Value Proposition — Why Not Just M365 Copilot? (2 min)

### The Differentiation Table (show on slide)

| Capability | M365 Copilot | Work IQ Agent |
|---|---|---|
| Find a vendor email | ✅ If you ask the right question | ✅ Also proactive |
| Cross-reference emails against contract terms | ❌ | ✅ Automatic |
| Track commitments across meetings + email | ❌ | ✅ Continuous |
| Flag SLA breaches before they happen | ❌ | ✅ Proactive alerts |
| Monitor task completion against deadlines | ❌ | ✅ With escalation |
| Draft context-aware follow-up communications | ✅ Generic | ✅ With contract terms embedded |
| Surface hidden penalty clauses | ❌ | ✅ Commercial intelligence |
| Role-based answer redaction (fail-closed) | ❌ | ✅ Explicit governance notes |
| Automated multi-sheet Excel reports | ❌ | ✅ On-demand + scheduled |
| Write back to enterprise trackers | ❌ | ✅ MCP update_entity |
| CDC reconciliation with human approval | ❌ | ✅ Audit-trailed |

### Quantified ROI

| Metric | Before (Manual) | After (Work IQ Agent) |
|--------|-----------------|------------------------|
| Vendor review prep time | 4–8 hours/month | **< 5 minutes** |
| SLA breach credits captured | ~20% (discovered at monthly review) | **100% flagged proactively** |
| Overdue commitment detection | At next monthly review | **Within hours** |
| Cross-reference accuracy | Relies on PM memory | **Complete** (every email × every contract clause) |
| JC readiness report assembly | 1–2 days across teams | **On-demand, automated** |
| Regulatory compliance gaps | Found during audit prep | **Continuously monitored** |
| Commercial leverage awareness | Scattered in confidential emails | **Auto-surfaced to leadership** |
| Vendor follow-up response time | Days (when someone notices) | **Same-day automated draft** |

### The One-Liner

> "M365 Copilot finds a vendor email if you ask. Our agent finds the SLA breach hiding in a confidential email thread, cross-references it against the contract penalty clause, alerts leadership with days of lead time, and generates a downloadable Excel report — all without anyone asking."

---

## 9. Pre-Demo Checklist

### Environment Setup

```powershell
# Terminal 1: Start the A2A simulator
$env:WORKIQ_SIM_SCENARIO = "scenarios/c1-northbridge"
$env:WORKIQ_SIM_PERSONA = "ops_director"
.\.venv\Scripts\python.exe simulator\a2a_server.py

# Terminal 2: Start sub-agents (Intent → Planner → Citation)
.\.venv\Scripts\python.exe agent\subagents\intent_agent.py
# (in separate terminals or use the launch scripts)
.\.venv\Scripts\python.exe agent\subagents\planner_agent.py
.\.venv\Scripts\python.exe agent\subagents\citation_agent.py

# Terminal 3: Start Web UI
.\.venv\Scripts\python.exe agent\web.py
# Open http://127.0.0.1:8000
```

### Pre-flight Checks

- [ ] All 4 services running (simulator:8920, intent:8930, planner:8931, citation:8932)
- [ ] Web UI loads at http://127.0.0.1:8000
- [ ] Test query returns cited answer
- [ ] Persona is set to `ops_director` (full access for main demo)
- [ ] Have a second terminal ready with `quality_pm` persona for the RBAC demo
- [ ] Azure AI Foundry endpoint is configured and responding
- [ ] Slide deck open with architecture diagram and differentiation table

### Demo Question Quick Reference

| # | Type | Question | Key Point |
|---|------|----------|-----------|
| S1 | Single-Signal | "What did the quality steering committee decide about the medication-reconciliation policy?" | Grounding fidelity — one source, exact citations |
| S2 | Single-Signal | "What is the current status of the MediTech Biomedical contract?" | Vendor 360° — tracker + emails + MSA document |
| M1 | Multi-Signal | "What is the current status of the EHR rollout at Westgate?" | Cross-signal — Teams + meetings correlated |
| M2 | Multi-Signal | "Which corrective actions are stalled and why?" | Meetings + emails + tracker — the "why" comes from email |
| M3 | Multi-Signal | "Which vendor contracts are coming up for renewal?" | Procurement intelligence — restricted email governance |
| A1 | Agentic | "Prep me for the Joint Commission readiness review" | 4+ sources, cross-committee, RBAC demo |
| W1 | Write-Back | "Update every open corrective action and flag past-due ones" | Agent executes writes — not just advises |
| W2 | Report | "Generate the weekly vendor status report" | On-demand Excel — replaces 4–8 hour manual process |
| G1 | Guardrail | "What is the capital of France?" | Scope refusal — strict, non-negotiable |

---

## 10. Appendix — Full Citation Reference

### Emails

| Citation ID | Subject | From → To | Key Content |
|-------------|---------|-----------|-------------|
| EML-001 | Westgate go-live update | Lumina (Tom Becker) → Northbridge | Build configured, training ~80%, holding 22-JUN target |
| EML-002 | RE: Westgate go-live | Robert Klein → Lumina | Requested written confirmation of migration validation + go-live date |
| EML-003 | Confidential: MSA commercial terms | Leadership only | MSA clause 7.4 — 8% credit/week if Lumina-side delay |
| EML-005 | Corrective action status | Angela Foster | CAPA-001 stalled waiting on David Munoz's workflow steps; CAPA-004 blocked on vendor quote |
| EML-006 | Credentialing update | Sandra Okafor | Onboarding gap closed, CAPA-002 Closed |
| EML-007 | Biomedical calibration schedule | MediTech → Karen Liu | Westgate monitors (14-JUL) & autoclave (18-JUL) scheduled |
| EML-008 | RE: Biomedical calibration | Karen Liu → MediTech | Access confirmed; certs needed within 48h |
| EML-009 | Delivery delay — audit log binders | PharmaLink → Karen Liu | Controlled-substance binders delayed to 16-JUL |
| EML-010 | RE: Delivery delay | Karen Liu → PharmaLink | SLA clause 5.2 invoked if further delay |
| EML-011 | CPOE upgrade v4.2 patch | ClearPoint → Karen Liu | v4.2 targeting 17-JUL staging, 21-JUL prod |
| EML-013 | Weekly vendor status roll-up | Karen Liu → James Whitaker | All-vendor weekly summary (restricted) |
| EML-014 | Contract renewal calendar Q3 | Marcus Webb → Karen Liu | Renewal actions for 3 vendors (restricted) |

### Meetings

| Citation ID | Title | Date | Key Content |
|-------------|-------|------|-------------|
| MTG-001 | Quality Steering Committee | 10-JUN | Adopted medication-reconciliation policy, CAPA-001 ownership |
| MTG-002 | Quality Steering Committee | 27-MAY | Prior quality meeting — CAPA-004 environment-of-care |
| MTG-003 | Credentialing Committee | 05-JUN | Closed provider-onboarding gap, CAPA-002 → Closed |
| MTG-004 | EHR Rollout Review | 09-JUN | Westgate go-live 22-JUN, migration validation blocker |
| MTG-005 | Monthly Vendor Performance Review | 10-JUL | All 4 vendors reviewed; MediTech renewal, PharmaLink rebid |

### Teams Messages

| Citation ID | Channel | Author | Key Content |
|-------------|---------|--------|-------------|
| MSG-001 | EHR Rollout Program | — | Migration validation 90% complete, on track |
| MSG-002 | EHR Rollout Program | — | Training ~80%, trainers booked through 20-JUN |
| MSG-006 | Vendor Management | Karen Liu | Portfolio: 4 vendors, PharmaLink amber |
| MSG-008 | Vendor Management | Marcus Webb | Contract renewal heads-up |
| MSG-010 | Vendor Management | Karen Liu | Weekly JC vendor readiness summary |

### Files

| Citation ID | Name | Key Content |
|-------------|------|-------------|
| FILE-003 | HR Credentialing Personnel File | HR-sensitive — restricted to credentialing lead |
| FILE-004 | JC Readiness Checklist | CAPA-001 and CAPA-004 on critical path |
| FILE-005 | Vendor Contract Portfolio Summary Q3 | All 4 vendor contracts, values, SLA status |
| FILE-006 | MediTech MSA & SLA Schedule | Full MSA terms, 10% service credit — restricted |
| FILE-007 | PharmaLink Distribution Agreement | 5% delay credit clause 5.2 — restricted |
| FILE-008 | ClearPoint License & Support | 99.5% uptime SLA, Appendix C JC mapping — restricted |

### Vendor Contract Tracker

| Citation ID | Vendor | Value | SLA Status | Service Credit Clause |
|-------------|--------|-------|------------|----------------------|
| VND-001 | Lumina Health Systems | $1.2M | Green | 8% impl. fee/week of delay |
| VND-002 | MediTech Biomedical | $340K | Green | 10% monthly fee/month of breach |
| VND-003 | PharmaLink Distributors | $520K | Amber | 5% line-item value/week of delay |
| VND-004 | ClearPoint Clinical Solutions | $280K | Green | 5% monthly license/month below 99.5% uptime |

### CAPA Tracker

| Citation ID | Action | Owner | Status | Past Due |
|-------------|--------|-------|--------|----------|
| CAPA-001 | Medication-reconciliation policy finalisation | Angela Foster | Open | Yes (due 09-JUN) |
| CAPA-002 | Provider-onboarding verification gap | Sandra Okafor | Closed | No |
| CAPA-003 | Westgate medication-list migration validation | Greg Sullivan | Open | No (due 13-JUN) |
| CAPA-004 | Westgate environment-of-care documentation | Priya Raman | Open | Yes (due 06-JUN) |

---

## Key Phrases for the Demo

Use these sound bites throughout your presentation:

- **"Cross-signal correlation"** — stitching emails + meetings + Teams into one answer
- **"Fail-closed governance"** — restricted data is never silently omitted
- **"Proactive intelligence"** — the agent finds risks before anyone asks
- **"Operational agent, not a chatbot"** — it writes back to trackers, generates reports
- **"Every claim is cited"** — zero hallucination, full audit trail
- **"Same agent code, swap the endpoint"** — simulator → production with no architecture changes
- **"Human-in-the-loop approval"** — CDC reconciliation requires explicit approval before writes

---

*Built on: Microsoft Agent Framework · Azure AI Foundry (GPT-4o-mini) · Work IQ (MCP + A2A) · Azure AI Search · FastAPI · OpenTelemetry*
