"""Generate the Vendor Evaluation & Procurement Agent design document as a Word file."""
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from pathlib import Path

doc = Document()

# Title
title = doc.add_heading("Vendor Evaluation & Procurement Agent", level=0)
title.alignment = WD_ALIGN_PARAGRAPH.CENTER

doc.add_paragraph(
    "Design Document — Work IQ Agent-Managed Vendor Proposal Evaluation\n"
    "Northbridge Health Network  |  August 2026"
).alignment = WD_ALIGN_PARAGRAPH.CENTER

doc.add_paragraph("")

# 1. Executive Summary
doc.add_heading("1. Executive Summary", level=1)
doc.add_paragraph(
    "Northbridge Health Network is expanding its vendor management capabilities to include "
    "agent-driven evaluation of new vendor proposals before onboarding. Currently, four vendors "
    "are under active contract management. This initiative extends the Work IQ agent to handle "
    "the pre-onboarding procurement lifecycle — from defining evaluation criteria through "
    "automated scoring, ranking, and side-by-side comparison of vendor proposals."
)
doc.add_paragraph(
    "The agent will monitor incoming RFP responses (via email, Teams, and document uploads), "
    "automatically extract proposal details, score them against predefined evaluation criteria, "
    "and surface ranked recommendations with supporting evidence for the evaluation panel."
)

# 2. Use Case
doc.add_heading("2. Use Case: Pre-Onboarding Vendor Evaluation", level=1)
doc.add_paragraph(
    "Northbridge has issued three RFPs for operational needs. Vendor candidates submit proposals "
    "through email and document uploads. The Work IQ agent:"
)
bullets = [
    "Defines and recommends evaluation criteria (cost, TCO, performance, compliance, references).",
    "Automatically reviews vendor submissions and RFP responses received via email or shared documents.",
    "Scores and ranks vendor proposals against weighted criteria for shortlisting.",
    "Surfaces supporting evidence and documents for the evaluation panel.",
    "Provides side-by-side vendor comparison using Work IQ insights.",
    "Logs all proposals and scores into a vendor_proposal_tracker table for audit trail.",
    "(Stretch) Captures and analyzes vendor presentations conducted in Teams meetings.",
]
for b in bullets:
    doc.add_paragraph(b, style="List Bullet")

# 3. Procurement Lifecycle
doc.add_heading("3. Procurement Lifecycle Stages", level=1)
stages = [
    ("Stage 1: RFP Definition", "Marcus Webb (Procurement Lead) defines requirements and evaluation criteria. "
     "The agent recommends standard criteria and weights based on the procurement category."),
    ("Stage 2: Proposal Collection", "Vendors submit proposals via email to Marcus Webb. Documents are uploaded "
     "to SharePoint. The agent detects new proposals and extracts key data points."),
    ("Stage 3: Automated Scoring", "The agent scores each proposal against the evaluation criteria matrix. "
     "Scores are logged in the vendor_proposal_tracker table with justification citations."),
    ("Stage 4: Panel Review", "The evaluation panel (Marcus Webb, Karen Liu, James Whitaker) reviews agent-generated "
     "rankings, side-by-side comparisons, and supporting evidence."),
    ("Stage 5: Shortlisting & Decision", "Top-ranked vendors are shortlisted. The agent generates a recommendation "
     "memo with scoring breakdown and risk flags."),
]
for title_text, desc in stages:
    doc.add_heading(title_text, level=2)
    doc.add_paragraph(desc)

# 4. Evaluation Criteria
doc.add_heading("4. Evaluation Criteria Framework", level=1)
doc.add_paragraph("The agent uses a weighted scoring matrix (1–10 scale) across these dimensions:")
table = doc.add_table(rows=8, cols=3)
table.style = "Light Grid Accent 1"
headers = ["Criterion", "Weight", "Description"]
for i, h in enumerate(headers):
    table.rows[0].cells[i].text = h
criteria = [
    ("Cost & TCO", "20%", "Upfront cost, total cost of ownership over contract term, hidden fees"),
    ("Technical Capability", "20%", "Solution fit, integration readiness, scalability, technology stack"),
    ("Performance & SLA", "15%", "Proposed SLAs, response times, uptime guarantees, penalty clauses"),
    ("Compliance & Security", "15%", "HIPAA, Joint Commission, DEA, data security certifications"),
    ("Implementation Plan", "10%", "Timeline, resource commitment, training plan, go-live approach"),
    ("Vendor Stability", "10%", "Financial health, market presence, client references, track record"),
    ("Innovation & Roadmap", "10%", "Product roadmap, R&D investment, AI/automation capabilities"),
]
for i, (crit, weight, desc) in enumerate(criteria):
    row = table.rows[i + 1]
    row.cells[0].text = crit
    row.cells[1].text = weight
    row.cells[2].text = desc

# 5. Open RFPs
doc.add_heading("5. Active RFPs", level=1)

doc.add_heading("RFP-001: Telehealth Platform", level=2)
doc.add_paragraph(
    "Northbridge is seeking a telehealth platform to support remote patient consultations across "
    "all network clinics. Requirements include video conferencing, EHR integration (with LuminaEHR), "
    "e-prescribing support, HIPAA compliance, and mobile app availability. Budget: $150K–$250K/year."
)

doc.add_heading("RFP-002: Clinical Analytics & Reporting", level=2)
doc.add_paragraph(
    "A clinical analytics platform for population health management, quality metrics dashboards, "
    "and regulatory reporting. Must integrate with LuminaEHR and ClearPoint CPOE. Requirements "
    "include real-time dashboards, Joint Commission report templates, and predictive analytics. "
    "Budget: $100K–$180K/year."
)

doc.add_heading("RFP-003: Medical Waste Management", level=2)
doc.add_paragraph(
    "A licensed medical waste disposal and compliance service for all Northbridge facilities. "
    "Requirements include scheduled pickups, emergency collection, DOT-compliant transport, "
    "manifesting/tracking portal, and staff training. Budget: $60K–$100K/year."
)

# 6. Vendor Candidates
doc.add_heading("6. Vendor Candidates", level=1)

rfp_vendors = {
    "RFP-001 (Telehealth)": [
        ("VirtuCare Health", "Founded 2019, 200+ healthcare clients, strong EHR integrations"),
        ("TeleMedix Solutions", "10-year track record, largest telehealth provider in the Midwest"),
        ("HealthBridge Connect", "Startup with AI-powered triage, competitive pricing"),
    ],
    "RFP-002 (Clinical Analytics)": [
        ("Meridian Data Sciences", "Enterprise analytics, 50+ hospital deployments, HL7/FHIR native"),
        ("InsightHealth Analytics", "Cloud-native, strong Joint Commission reporting templates"),
    ],
    "RFP-003 (Medical Waste)": [
        ("EnviroMed Disposal", "Regional leader, 15 years in healthcare waste, DOT-certified fleet"),
        ("GreenHealth Waste Services", "National provider, sustainability-focused, competitive rates"),
    ],
}
for rfp, vendors in rfp_vendors.items():
    doc.add_heading(rfp, level=2)
    for name, desc in vendors:
        doc.add_paragraph(f"{name} — {desc}", style="List Bullet")

# 7. Personas
doc.add_heading("7. New Personas & Roles", level=1)
doc.add_paragraph(
    "All external vendor candidates report to Marcus Webb (PPL-015, Procurement & Sourcing Lead) "
    "as the internal point of contact. The evaluation panel consists of:"
)
panel = [
    ("Marcus Webb (PPL-015)", "Procurement Lead — owns the RFP process, collects proposals, manages vendor communications"),
    ("Karen Liu (PPL-011)", "Vendor/Contract Manager — evaluates commercial terms, SLA feasibility, contract risk"),
    ("James Whitaker (PPL-002)", "Director of Operations — final approval authority, strategic alignment"),
]
for name, role in panel:
    doc.add_paragraph(f"{name}: {role}", style="List Bullet")

doc.add_paragraph("\nNew external vendor personas (proposal submitters):")
vendor_personas = [
    ("procurement_eval", "Marcus Webb — Procurement Evaluation Lead", "Sees all RFPs, all proposals, scoring, rankings. Primary evaluator."),
    ("virtucare_vendor", "Dana Mitchell — VirtuCare Health (Sales Director)", "External vendor. Sees only VirtuCare-related correspondence and RFP-001."),
    ("telemedix_vendor", "Ryan Patel — TeleMedix Solutions (VP Sales)", "External vendor. Sees only TeleMedix correspondence and RFP-001."),
    ("healthbridge_vendor", "Sofia Reyes — HealthBridge Connect (CEO)", "External vendor. Sees only HealthBridge correspondence and RFP-001."),
    ("meridian_vendor", "Alex Thornton — Meridian Data Sciences (Account Dir)", "External vendor. Sees only Meridian correspondence and RFP-002."),
    ("insighthealth_vendor", "Priya Kapoor — InsightHealth Analytics (Sales Mgr)", "External vendor. Sees only InsightHealth correspondence and RFP-002."),
    ("enviromed_vendor", "Carlos Mendez — EnviroMed Disposal (Regional Mgr)", "External vendor. Sees only EnviroMed correspondence and RFP-003."),
    ("greenhealth_vendor", "Laura Kim — GreenHealth Waste Services (Acct Mgr)", "External vendor. Sees only GreenHealth correspondence and RFP-003."),
]
for pid, label, desc in vendor_personas:
    doc.add_paragraph(f"{pid}: {label} — {desc}", style="List Bullet")

# 8. Agent Capabilities
doc.add_heading("8. Agent Capabilities for Vendor Evaluation", level=1)
capabilities = [
    ("Proposal Ingestion", "When a vendor email/document arrives, the agent extracts proposal data "
     "(pricing, SLAs, implementation timeline, references) and creates a row in vendor_proposal_tracker."),
    ("Criteria Recommendation", "On request, the agent recommends evaluation criteria and weights "
     "based on the RFP category (healthcare IT, clinical supplies, facilities services)."),
    ("Automated Scoring", "The agent scores each proposal (1–10) on each criterion using evidence "
     "from the proposal document, emails, and Teams messages. Justification is cited."),
    ("Ranking & Shortlisting", "The agent computes weighted total scores, ranks proposals per RFP, "
     "and highlights the top candidates with a risk/opportunity summary."),
    ("Side-by-Side Comparison", "On request, the agent generates a comparison table across all "
     "proposals for a given RFP, with strengths/weaknesses for each vendor."),
    ("Meeting Analysis (Stretch)", "When a vendor presentation Teams meeting occurs, the agent "
     "extracts key claims, commitments, and evaluation-relevant data from the recap."),
]
for title_text, desc in capabilities:
    doc.add_heading(title_text, level=2)
    doc.add_paragraph(desc)

# 9. Data Model
doc.add_heading("9. vendor_proposal_tracker Table Schema", level=1)
doc.add_paragraph("Each proposal logged by the agent has these fields:")
schema_table = doc.add_table(rows=15, cols=3)
schema_table.style = "Light Grid Accent 1"
schema_headers = ["Field", "Type", "Description"]
for i, h in enumerate(schema_headers):
    schema_table.rows[0].cells[i].text = h
fields = [
    ("id", "string", "Unique proposal ID (PROP-001, PROP-002, ...)"),
    ("rfp_id", "string", "Which RFP this responds to (RFP-001, RFP-002, RFP-003)"),
    ("vendor_name", "string", "Name of the proposing vendor"),
    ("vendor_contact", "string", "Person ID of the vendor contact"),
    ("submitted_date", "date", "When the proposal was received"),
    ("proposal_summary", "string", "Agent-extracted summary of the proposal"),
    ("proposed_cost", "string", "Proposed annual cost / total cost"),
    ("proposed_timeline", "string", "Implementation timeline proposed"),
    ("score_cost", "int (1-10)", "Agent score for Cost & TCO"),
    ("score_technical", "int (1-10)", "Agent score for Technical Capability"),
    ("score_sla", "int (1-10)", "Agent score for Performance & SLA"),
    ("score_compliance", "int (1-10)", "Agent score for Compliance & Security"),
    ("weighted_total", "float", "Computed weighted total score"),
    ("status", "string", "Received / Scored / Shortlisted / Rejected / Selected"),
]
for i, (field, typ, desc) in enumerate(fields):
    row = schema_table.rows[i + 1]
    row.cells[0].text = field
    row.cells[1].text = typ
    row.cells[2].text = desc

# Save
out = Path(__file__).resolve().parent / "VENDOR_EVALUATION_DESIGN.docx"
doc.save(str(out))
print(f"Saved: {out}")
