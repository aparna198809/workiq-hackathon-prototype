# Vendor Contract Management — New Entities & Data Map

## Overview

Three new vendors have been added to the Northbridge Health Network (c1-northbridge) scenario to support the **Vendor Contract Management** use case. These vendors cover the three contract categories:

| # | Vendor | Category | Contract ID |
|---|--------|----------|-------------|
| 1 | **MediTech Biomedical Inc.** | Medical & Biomedical Equipment | VND-002 |
| 2 | **PharmaLink Distributors** | Clinical Supplies & Pharmacy Distribution | VND-003 |
| 3 | **ClearPoint Clinical Solutions** | Clinical Software (CPOE & Lab) | VND-004 |

The existing vendor **Lumina Health Systems** (EHR & Clinical Software) is formalized as VND-001.

---

## New Entities Created

### People (people.json)

| ID | Name | Role | Organization | Type |
|----|------|------|--------------|------|
| PPL-011 | Karen Liu | Vendor/Contract Manager (VMO) | Northbridge — Procurement & Vendor Management | Internal |
| PPL-012 | Rachel Torres | Account Manager | MediTech Biomedical Inc. | Vendor |
| PPL-013 | Steve Nakamura | Regional Manager | PharmaLink Distributors | Vendor |
| PPL-014 | Lisa Chen | Account Director | ClearPoint Clinical Solutions | Vendor |
| PPL-015 | Marcus Webb | Procurement & Sourcing Lead | Northbridge — Procurement & Vendor Management | Internal |

### Personas (personas.json)

| ID | Label | Description |
|----|-------|-------------|
| vendor_manager | Karen Liu — VMO | Sees all vendor contracts, SLA performance, commitments, escalations, and commercial terms. Does NOT see HR-sensitive credentialing material. |

### Stakeholder Mapping

| Stakeholder Role | Person | ID | What They See |
|-----------------|--------|----|---------------|
| Vendor/Contract Manager (VMO) | Karen Liu | PPL-011 | All vendor data, SLA reports, contract terms, escalations |
| Procurement/Sourcing Lead | Marcus Webb | PPL-015 | Renewal calendar, rebid recommendations, vendor evaluations |
| Category Manager — IT & Software | Robert Klein | PPL-004 | Lumina (EHR) + ClearPoint (CPOE) contracts |
| Category Manager — Compliance/Equipment | Priya Raman | PPL-007 | MediTech calibration and JC equipment standards |
| Category Manager — Pharmacy Operations | David Munoz | PPL-006 | PharmaLink supply chain, controlled-substance compliance |

---

## Vendor Contract Tracker (tables/vendor_contract_tracker.json) — NEW TABLE

Each contract record tracks the fields specified in the requirements:

| Field | Description |
|-------|-------------|
| `id` | Unique vendor contract ID (VND-xxx) |
| `vendor_name` | Legal vendor name |
| `vendor_contact` | People ID of vendor primary contact |
| `category` | Contract category (EHR, Equipment, Supplies, Software) |
| `contract_type` | Type of agreement (MSA, License, Distribution, etc.) |
| `contract_value` | Annual contract value |
| `start_date` / `end_date` | Contract term |
| `renewal_type` | Auto-renewal vs fixed term, notice period |
| `sla_response_hours` | SLA response time commitments |
| `sla_uptime` | Uptime SLA (where applicable) |
| `service_credit_clause` | Penalty/credit terms for SLA breach |
| `performance_kpi` | Key performance indicators tracked |
| `compliance_requirements` | Joint Commission and regulatory requirements |
| `status` | Current contract status |
| `current_sla_status` | Green / Amber / Red |
| `owner` | VMO owner (People ID) |
| `internal_category_manager` | Internal category manager (People ID) |
| `open_commitments` | Count of open vendor commitments |
| `next_milestone` | Next upcoming milestone |
| `acl` | Access control list |

### Contract Summary

| VND ID | Vendor | Category | Value | SLA Status | Renewal | Service Credit |
|--------|--------|----------|-------|------------|---------|----------------|
| VND-001 | Lumina Health Systems | EHR & Clinical Software | $1.2M | Green | 01-MAR-2027 (120-day notice) | 8% of impl. fee/week of delay |
| VND-002 | MediTech Biomedical | Medical & Biomedical Equipment | $340K | Green | 01-SEP-2026 (auto, 60-day notice) | 10% monthly fee/month of breach |
| VND-003 | PharmaLink Distributors | Clinical Supplies & Pharmacy | $520K | Amber | 15-OCT-2026 (90-day rebid notice) | 5% line-item value/week of delay |
| VND-004 | ClearPoint Clinical Solutions | Clinical Software (CPOE & Lab) | $280K | Green | 01-MAR-2027 (120-day notice) | 5% monthly license/month below 99.5% uptime |

---

## Emails Added (emails.json)

| ID | Thread | Subject | From → To | Key Content |
|----|--------|---------|-----------|-------------|
| EML-007 | THR-MEDITECH-CALIBRATION | Biomedical calibration schedule | Rachel Torres → Karen Liu | Westgate patient monitors (14-JUL) & autoclave (18-JUL) scheduled |
| EML-008 | THR-MEDITECH-CALIBRATION | RE: Biomedical calibration | Karen Liu → Rachel Torres | Access confirmed; certs needed within 48h |
| EML-009 | THR-PHARMALINK-SUPPLY | Delivery delay — audit log binders | Steve Nakamura → Karen Liu | Controlled-substance binders delayed to 16-JUL |
| EML-010 | THR-PHARMALINK-SUPPLY | RE: Delivery delay | Karen Liu → Steve Nakamura | SLA clause 5.2 invoked if further delay |
| EML-011 | THR-CLEARPOINT-CPOE | CPOE upgrade v4.2 patch | Lisa Chen → Karen Liu | v4.2 targeting 17-JUL staging, 21-JUL prod |
| EML-012 | THR-CLEARPOINT-CPOE | RE: CPOE upgrade | Karen Liu → Lisa Chen | HL7 feed activation coordinated for 15-JUL |
| EML-013 | THR-VENDOR-WEEKLY | Weekly vendor status roll-up | Karen Liu → James Whitaker | All-vendor weekly summary (restricted) |
| EML-014 | THR-VENDOR-COMMERCIAL | Contract renewal calendar Q3 | Marcus Webb → Karen Liu | Renewal actions for MediTech, PharmaLink, ClearPoint (restricted) |

---

## Teams Messages Added (teams.json)

| ID | Channel | Author | Key Content |
|----|---------|--------|-------------|
| MSG-006 | Vendor Management | Karen Liu | Portfolio update: 4 vendors, PharmaLink amber |
| MSG-007 | Vendor Management | Karen Liu | MediTech calibration dates confirmed |
| MSG-008 | Vendor Management | Marcus Webb | Contract renewal heads-up |
| MSG-009 | Vendor Management | Robert Klein | ClearPoint HL7 feed coordination |
| MSG-010 | Vendor Management | Karen Liu | Weekly JC vendor readiness summary |

---

## Meeting Added (meetings.json)

| ID | Title | Date | Attendees | Key Decisions |
|----|-------|------|-----------|---------------|
| MTG-005 | Monthly Vendor Performance Review | 10-JUL-2026 | Karen Liu, James Whitaker, Marcus Webb, Priya Raman, Maria Delgado | Reviewed all 4 vendors; MediTech renewal recommended; PharmaLink rebid flagged; ClearPoint JC compliance confirmed |

**Action Items from MTG-005:**

| AI ID | Action | Owner | Due |
|-------|--------|-------|-----|
| AI-501 | Obtain MediTech calibration certs within 48h | Karen Liu | 20-JUL |
| AI-502 | Confirm PharmaLink binder delivery by 16-JUL | Karen Liu | 16-JUL |
| AI-503 | Coordinate HL7 feed activation (Lumina ↔ ClearPoint) | Robert Klein | 15-JUL |
| AI-504 | Prepare MediTech MSA renewal recommendation | Marcus Webb | 25-JUL |
| AI-505 | Draft rebid scope for PharmaLink controlled-substance segment | Marcus Webb | 01-AUG |

---

## Files Added (files.json)

| ID | Name | Type | Sensitivity | Key Content |
|----|------|------|-------------|-------------|
| FILE-005 | Vendor Contract Portfolio Summary — Q3 2026.xlsx | Spreadsheet | Internal | All 4 vendor contracts, values, SLA status, renewals |
| FILE-006 | MediTech Biomedical — MSA & SLA Schedule.pdf | Document | Restricted | Full MSA terms, 48h/4h SLA, 10% service credit |
| FILE-007 | PharmaLink — Distribution Agreement.pdf | Document | Restricted | Distribution terms, 5% delay credit (clause 5.2) |
| FILE-008 | ClearPoint — License & Support Agreement.pdf | Document | Restricted | License terms, 99.5% uptime SLA, Appendix C JC mapping |

---

## Golden Questions Added (golden.json)

| ID | Tier | Question | Automation Scenario |
|----|------|----------|---------------------|
| Q9 | agent-automation | Generate the weekly vendor and commitment status report | **Weekly Vendor & Commitment Status** |
| Q10 | agent-automation | Generate the Joint Commission readiness report (vendor compliance) | **Joint Commission Readiness Report** |
| Q11 | single-signal | MediTech contract status and open commitments | Vendor 360 deep dive |
| Q12 | multi-signal | Vendor contract renewals and procurement recommendations | Renewal portfolio scan |

---

## Entity Cross-Reference Map

```
┌─────────────────────────────────────────────────────────────┐
│                    VENDOR CONTRACT TRACKER                    │
│              (vendor_contract_tracker.json)                   │
├──────────┬───────────────┬──────────────────────────────────┤
│ VND-001  │ Lumina        │ EHR & Clinical Software          │
│ VND-002  │ MediTech      │ Medical & Biomedical Equipment   │
│ VND-003  │ PharmaLink    │ Clinical Supplies & Pharmacy     │
│ VND-004  │ ClearPoint    │ Clinical Software (CPOE & Lab)   │
└──────────┴───────┬───────┴──────────────────────────────────┘
                   │
    ┌──────────────┼──────────────────────────┐
    │              │                          │
    ▼              ▼                          ▼
┌────────┐  ┌────────────┐  ┌──────────────────────────┐
│ PEOPLE │  │   EMAILS   │  │    TEAMS MESSAGES        │
├────────┤  ├────────────┤  ├──────────────────────────┤
│PPL-008 │◄─│ EML-001/02 │  │ MSG-001..003 (EHR)       │
│  Lumina│  │ EML-003/04 │  │ MSG-006..010 (Vendor Mgmt│
│PPL-012 │◄─│ EML-007/08 │  └──────────────────────────┘
│MediTech│  │ EML-009/10 │
│PPL-013 │◄─│ EML-011/12 │  ┌──────────────────────────┐
│PharmaLk│  │ EML-013/14 │  │    MEETINGS              │
│PPL-014 │◄─└────────────┘  ├──────────────────────────┤
│ClearPt │                  │ MTG-004 (EHR rollout)     │
├────────┤                  │ MTG-005 (Vendor review)   │
│PPL-011 │─── VMO Owner     └──────────────────────────┘
│PPL-015 │─── Procurement
└────────┘                  ┌──────────────────────────┐
                            │    FILES                  │
    ┌────────────┐          ├──────────────────────────┤
    │  PERSONAS  │          │ FILE-005 Portfolio Summary│
    ├────────────┤          │ FILE-006 MediTech MSA     │
    │vendor_mgr  │──►PPL-011│ FILE-007 PharmaLink Agree│
    │ops_director│──►PPL-002│ FILE-008 ClearPoint Lic.  │
    │quality_pm  │──►PPL-001└──────────────────────────┘
    │cred_lead   │──►PPL-003
    │vendor_lias.│──►PPL-008
    └────────────┘
```

---

## Source Systems Mapped

| Source System | Platform | Data Surfaced | Integration | Access |
|---------------|----------|---------------|-------------|--------|
| Outlook / Exchange | M365 | Vendor correspondence (EML-007..014), escalations, commitments | Native work graph | Read |
| Teams (chats & channels) | M365 | Vendor Management channel (MSG-006..010), coordination | Native | Read |
| Meetings & transcripts | M365 | Vendor Performance Review (MTG-005), action items | Native | Read |
| SharePoint / OneDrive | M365 | SOWs, contracts, portfolio summary (FILE-005..008) | Native | Read |
| People graph | M365 | Vendor contacts, VMO ownership, reporting lines | Native | Read |
| Dataverse trackers | Native | Vendor contract tracker (VND-001..004), CAPA tracker | Tools | R/W |
