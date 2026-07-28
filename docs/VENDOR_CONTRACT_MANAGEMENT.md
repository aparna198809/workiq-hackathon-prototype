# Vendor & Contract Management Agent
## Built on Microsoft WorkIQ + Azure AI Foundry

---

## The Pain

Vendor commitments, escalations, and SLA breaches live in **scattered email, meetings, and a contract/ITSM system**. The monthly vendor review is reconstructed by hand — by then, commercial leverage has expired and penalty windows have passed.

> **Real example from our data:** Northbridge's MSA clause 7.4 entitles them to an 8% service credit per week if Lumina's go-live slips — but this intelligence lives in a single confidential email between two executives. Without proactive monitoring, leadership misses the activation window entirely.

---

## What the Agent Does

Consolidates vendor correspondence, meeting commitments, and connector data into **one portfolio view**; flags SLA breaches and overdue commitments; and drafts vendor follow-ups.

```
┌────────────────────────────────────────────────────────────────────┐
│              VENDOR & CONTRACT MANAGEMENT LOOP                       │
│                                                                      │
│   INGEST           CORRELATE        ALERT           ACT              │
│   ┌──────┐        ┌──────┐        ┌──────┐        ┌──────┐        │
│   │Vendor│───────▶│Cross-│───────▶│Flag  │───────▶│Draft │        │
│   │Emails│        │Ref   │        │SLA   │        │Follow│        │
│   │Meetings│      │Contract│      │Breach│        │-Up   │        │
│   │ITSM   │      │Terms  │        │Risk  │        │Escalate│     │
│   └──────┘        └──────┘        └──────┘        └──────┘        │
│       ▲                                                │            │
│       └────────────────────────────────────────────────┘            │
│                      Continuous Monitoring                           │
└────────────────────────────────────────────────────────────────────┘
```

---

## Signals Stitched

| Signal Source | What We Extract |
|---------------|-----------------|
| **Vendor email** | Commitments, ETAs, scope confirmations, escalation responses |
| **Meetings** | Decisions, action items assigned to vendors, approved scopes |
| **Contract / ITSM connector** | SLA windows, penalty clauses, service-credit triggers |
| **Work order trackers** | Vendor task status, overdue items, risk flags |

---

## Evidence from Our Scenarios

### 🔴 SLA Breach Risks Detected

| Scenario | Vendor | Risk | Contract Clause | Exposure |
|----------|--------|------|-----------------|----------|
| **C1-Northbridge** | Lumina Health Systems | Go-live slip past 22-JUN | MSA Clause 7.4 | 8% service credit / week of delay |
| **C4-Arundel** | Coolflow Mechanical | Chiller restoration > 14 days | Clause 6.2 | Service-credit schedule applies |
| **C2-Contoso** | Apex Alloys | Non-conforming material delivery | Penalty Clause 9.3 | Penalty for non-conforming lots |
| **C6-EDKH** | Atlas (internal SLA) | Payment outage > contractual window | Customer SLA | Fee waiver + SLA-credit exposure |

### 📋 Vendor Commitments Tracked

| Vendor | Commitment | Due Date | Status | Source |
|--------|-----------|----------|--------|--------|
| Lumina Health Systems | Written go-live confirmation | 11-JUN | ⏳ Pending | EML-002 + MTG-004 |
| Lumina Health Systems | Go-live Westgate 22-JUN | 22-JUN | ⚠️ At Risk (blocked by migration validation) | EML-001 |
| Coolflow Mechanical | Pressure-test, braze leak, restore chiller | 26-JUN | 🔧 In Progress | EML-004 + WO-001 |
| Coolflow Mechanical | Bishop House planned maintenance | 05-JUN | 🔴 **Overdue** | WO-003 |
| Apex Alloys | Conforming replacement lot 24-126 | 13-JUN | ⏳ Pending | EML-004, AI-101 |
| Brightwater (Client) | Cutover recovery | 26-JUN | 🔧 In Progress | EML-002, AI-101 |

### 🔗 Cross-Reference Intelligence (What Humans Miss)

**Example 1: Northbridge — Hidden Commercial Leverage**
- 📧 EML-003 (Confidential): MSA clause 7.4 = 8% credit/week if Lumina slips
- 📧 EML-005: Migration validation is blocked → Greg Sullivan past due
- 📅 MTG-004: Go-live blocker is the validation, due 13-JUN
- **Agent insight:** "Lumina go-live at risk. If slip is Lumina-side, clause 7.4 activates in 4 days. Recommend leadership review."

**Example 2: Arundel — Tenant Exposure + Vendor SLA**
- 📧 EML-004 (Coolflow): ETA 25-26 JUN for restoration
- 📄 FILE-002: SLA restore window = 14 days; credit clause 6.2 applies if missed
- 📧 EML-001 (Confidential): Anchor tenant on floors 18-24 has lease cooling-availability obligations
- **Agent insight:** "Coolflow SLA window expires 26-JUN. If restoration misses, clause 6.2 service credit triggers AND tenant contractual exposure is activated. 2-day buffer remaining."

**Example 3: Contoso — Supplier Quality + Penalty**
- 📧 EML-003: Apex Alloys lot 24-118 = 34 HRC (spec: 40-44 HRC)
- 📄 FILE-003: Penalty clause 9.3 applies for non-conforming lots
- 📄 FILE-002: Supplier risk register shows this as the #1 open risk
- 📅 MTG-001: Decision = quarantine + replacement + re-test, re-baselined to 03-JUL
- **Agent insight:** "Apex Alloys delivered non-conforming material. Penalty clause 9.3 is activatable. Customer Aeronix has formally escalated — recommend vendor commercial review."

---

## Demo Moments

### 1️⃣ "Coolflow's SLA credit activates in 2 days" (Proactive Alert)
No one asked. The agent cross-referenced the repair ETA against clause 6.2's window and flagged leadership before the credit window expired.

### 2️⃣ "Here's every open vendor commitment" (Portfolio View)
One prompt → consolidated table of all vendor commitments, due dates, statuses, and risk flags — pulled from emails, meetings, and work orders across the organization.

### 3️⃣ "Apex Alloys owes you under clause 9.3" (Commercial Intelligence)
Agent detected the material non-conformance, matched it to the penalty clause in the supplier agreement, and drafted an escalation note for procurement.

### 4️⃣ "Bishop House maintenance is 5 days overdue — draft vendor follow-up" (Automated Action)
Agent detected WO-003 overdue, found no rebooking email, and drafted a follow-up to Coolflow requesting a new maintenance window.

---

## Why Work IQ — Not Just Copilot

| Capability | M365 Copilot | Vendor & Contract Agent |
|---|---|---|
| Find a vendor email | ✅ (you ask) | ✅ (also proactive) |
| Cross-reference email against contract terms | ❌ | ✅ |
| Track commitments across meetings + email | ❌ | ✅ |
| Flag SLA breach before it happens | ❌ | ✅ |
| Monitor vendor task completion | ❌ | ✅ |
| Draft vendor follow-ups | ❌ | ✅ |
| Surface commercial leverage (penalty clauses) | ❌ | ✅ |

**Connector integration plus proactive, portfolio-scale monitoring across many vendors is an automation — not an interactive chat you drive one question at a time.**

---

## Quantified Value

| Metric | Before (Manual) | After (Agent) |
|--------|-----------------|---------------|
| Vendor review prep time | 4-8 hours/month | 5 minutes |
| SLA breach credits captured | ~20% (often missed) | 100% flagged |
| Overdue commitments detected | At monthly review | Within hours |
| Commercial leverage awareness | Scattered in confidential emails | Auto-surfaced to leadership |
| Vendor follow-up response time | Days (when someone notices) | Same-day automated draft |
| Cross-reference accuracy | Depends on PM memory | Complete — every email × every clause |

---

## Data Proof: What We Found Across 6 Scenarios

```
┌─────────────────────────────────────────────────────────────────┐
│  6 scenarios analyzed                                            │
│                                                                   │
│  4  Active SLA breach risks identified                           │
│  3  Penalty clauses activatable (7.4, 6.2, 9.3)                 │
│  6  Open vendor commitments with due dates                       │
│  2  Overdue vendor items (Bishop House PM, CAPA-004 quote)       │
│  3  Confidential commercial terms hidden in email                │
│  4  Client/customer escalations requiring vendor coordination    │
│                                                                   │
│  Without the agent: discovered at next monthly review (or audit) │
│  With the agent: flagged within hours, with citations            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Architecture

```
    Microsoft 365              ITSM / CMMS           Contract Store
    (vendor email,             (work orders,          (MSAs, SOWs,
     meetings, Teams)           maintenance)           SLA registers)
         │                          │                       │
         ▼                          ▼                       ▼
    ┌─────────────────────────────────────────────────────────────┐
    │           WorkIQ + Dataverse Connectors                      │
    └──────────────────────────┬──────────────────────────────────┘
                               ▼
    ┌─────────────────────────────────────────────────────────────┐
    │      Multi-Agent Orchestration (Azure AI Foundry)            │
    │                                                              │
    │  Intent → Planner (MCP tools) → Citation                    │
    │                                                              │
    │  Capabilities:                                               │
    │  • Extract commitments from email/meetings                   │
    │  • Cross-reference against contract clauses                  │
    │  • Monitor vendor task completion in CMMS                    │
    │  • Flag SLA window approaching/breached                      │
    │  • Draft follow-up communications                            │
    └──────────────────────────┬──────────────────────────────────┘
                               ▼
    ┌─────────────────────────────────────────────────────────────┐
    │  Actions:                                                    │
    │  • Teams alert to leadership (SLA window closing)            │
    │  • Draft vendor follow-up email                              │
    │  • Update vendor commitment tracker (Dataverse)              │
    │  • Generate vendor performance report                        │
    │  • Escalation workflow (Power Automate)                      │
    └─────────────────────────────────────────────────────────────┘
```

---

## Outcome

> **Every vendor's real status in one review — no manual reconstruction.**

The agent replaces the monthly scramble of "who said what, when was it due, did they deliver?" with a continuously updated portfolio view that flags risks before they become breaches and surfaces commercial leverage before it expires.

---

*Northbridge Health Network · Arundel Holdings · Contoso Manufacturing · Microsoft Work IQ*
