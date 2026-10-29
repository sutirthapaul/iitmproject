"""Generate synthetic (fictional) supplier RFP responses as PDFs.

All companies, people, clients and figures are invented for classroom use.

Usage:  python scripts/make_pdfs.py
Output: sample_rfps/*.pdf and sample_rfps/edge_cases/*.pdf
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

OUT = Path(__file__).resolve().parents[1] / "sample_rfps"
EDGE = OUT / "edge_cases"

RFP_TITLE = "Customer Service Platform Modernisation"
BUYER = "Meridian Retail Group (fictional)"
RFP_REF = "MRG-RFP-2026-014"

# --------------------------------------------------------------------------- content
# Each supplier: dict of section -> list of paragraphs, plus a price table.
# Profiles follow the brief: deliberately different strengths, gaps and evidence quality.

SUPPLIERS: dict[str, dict] = {
    "Apex Systems": {
        "file": "apex_systems_proposal.pdf",
        "tagline": "Enterprise engineering for mission-critical service platforms",
        "summary": [
            "Apex Systems is pleased to respond to RFP MRG-RFP-2026-014. We understand that Meridian Retail "
            "Group needs to replace three legacy contact-centre tools with a single omnichannel customer service "
            "platform that supports 1,200 agents today and 3,000 agents within three years, integrates with the "
            "existing Salesforce CRM, SAP S/4HANA order management and the Genesys telephony estate, and meets "
            "the security expectations of a listed retailer.",
            "Our proposal prioritises architectural robustness and security. It is not the lowest-cost option; "
            "it is designed to remain stable at peak trading volumes such as festive-season sales.",
        ],
        "solution": [
            "The platform uses a cloud-native microservices architecture deployed on Kubernetes across two "
            "availability zones with active-active failover. Each service (case management, routing, knowledge, "
            "analytics) scales horizontally through autoscaling policies tied to queue depth.",
            "Integration is delivered through a central API gateway with versioned REST APIs and an event bus "
            "(Apache Kafka). We provide pre-built connectors for Salesforce CRM, SAP S/4HANA and Genesys Cloud, "
            "with a documented integration specification for each interface, including field mappings, error "
            "handling and retry behaviour.",
            "Scalability evidence: in a load test for a comparable retailer the platform sustained 5,000 "
            "concurrent agents and 40,000 interactions per hour with p95 API latency under 300 ms. We commit "
            "to a 99.95% availability SLA.",
        ],
        "implementation": [
            "Delivery follows a 24-week plan in four phases: Discovery and Design (weeks 1-5), Build and "
            "Integration (weeks 6-15), Testing and UAT (weeks 16-20) and Rollout (weeks 21-24).",
            "Milestones: M1 solution design sign-off (week 5), M2 integrations complete (week 15), M3 UAT "
            "sign-off (week 20), M4 go-live (week 24).",
            "Team structure: one delivery manager, one solution architect, six engineers, two QA engineers and "
            "one security engineer. A risk register will be maintained and reviewed fortnightly with Meridian.",
        ],
        "price_rows": [
            ["Platform licences (3 years, 1,200 agents)", "$720,000"],
            ["Implementation services (fixed price)", "$360,000"],
            ["Integration connectors (Salesforce, SAP, Genesys)", "$110,000"],
            ["Training and change management", "$50,000"],
            ["Total contract value (3 years)", "$1,240,000"],
        ],
        "assumptions": [
            "Prices exclude applicable taxes. Implementation is fixed price; licences are invoiced annually in "
            "advance. Additional agents beyond 1,200 are priced at $180 per agent per year. Payment milestones "
            "are aligned to M1-M4. Total cost of ownership over three years is shown above; there are no "
            "additional mandatory fees.",
        ],
        "security": [
            "Apex Systems holds ISO/IEC 27001:2022 certification and a SOC 2 Type II report (audit period "
            "ending June 2026), both available under NDA.",
            "Data is encrypted at rest using AES-256 and in transit using TLS 1.3. Encryption keys are managed "
            "in a customer-dedicated KMS with key rotation every 90 days.",
            "Access control uses SSO via SAML 2.0, role-based access control (RBAC) and multi-factor "
            "authentication for all administrative users. Immutable audit logs are retained for 13 months and "
            "can be exported to Meridian's SIEM.",
            "We comply with GDPR and India's Digital Personal Data Protection (DPDP) Act 2023, support data "
            "residency in India, and commission an independent penetration test annually. A documented "
            "incident response plan commits to notifying Meridian within 24 hours of a confirmed incident.",
        ],
        "support": [
            "Support is provided 24x7 for Priority 1 incidents and during business hours (09:00-18:00 IST) for "
            "lower priorities. Response time targets: P1 30 minutes, P2 2 hours, P3 1 business day.",
            "Relevant experience: three omnichannel contact-centre implementations for retail and telecom "
            "clients in the last four years.",
            "References: Northwind Telecom (Head of Customer Operations) and Harbourline Retail (CIO). Contact "
            "details are provided in Annex C.",
        ],
    },
    "BrightPath Tech": {
        "file": "brightpath_tech_proposal.pdf",
        "tagline": "Fast, affordable digital transformation",
        "summary": [
            "BrightPath Tech is excited to propose an agile, low-cost route to a modern customer service "
            "platform for Meridian Retail Group. We understand Meridian wants to move quickly away from its "
            "legacy tools and keep costs under control.",
            "Our offer is the lowest total cost and the fastest timeline we believe Meridian will receive: "
            "go-live in 12 weeks.",
        ],
        "solution": [
            "We will configure our SaaS helpdesk product, BrightDesk, which provides ticketing, live chat, "
            "email and a basic knowledge base. The product is hosted on a public cloud and scales by adding "
            "instances as demand grows.",
            "Integration with Salesforce CRM is available through our standard REST API. Integration with SAP "
            "and Genesys can be built during the project using our API.",
        ],
        "implementation": [
            "We use a rapid 12-week delivery model: weeks 1-2 setup, weeks 3-9 configuration, weeks 10-11 "
            "testing, week 12 go-live.",
            "Our team will consist of a project lead and four consultants. We work in two-week sprints and "
            "will agree the detailed plan with Meridian after contract signature.",
        ],
        "price_rows": [
            ["BrightDesk subscription (3 years, 1,200 agents)", "$396,000"],
            ["Configuration and setup (fixed price)", "$129,000"],
            ["Training (online)", "$20,000"],
            ["Integrations (SAP, Genesys)", "$40,000"],
            ["Total contract value (3 years)", "$585,000"],
        ],
        "assumptions": [
            "All-inclusive fixed price for the scope described. Prices exclude taxes. Subscription billed "
            "annually. Integration effort assumes Meridian provides API documentation and test environments "
            "in week 1. Payment: 50% on signature, 50% on go-live.",
        ],
        "security": [
            "BrightPath follows industry best practices for security. Our hosting provider is a major cloud "
            "vendor with its own certifications.",
            "We are planning to begin ISO 27001 certification next year. A security questionnaire can be "
            "completed on request.",
        ],
        "support": [
            "Support is available by email during business hours, Monday to Friday.",
            "BrightPath was founded in 2023. We have completed two helpdesk deployments for small e-commerce "
            "businesses. References are available on request.",
        ],
    },
    "NexaWorks": {
        "file": "nexaworks_proposal.pdf",
        "tagline": "Balanced delivery. Lasting partnership.",
        "summary": [
            "NexaWorks welcomes the opportunity to respond to RFP MRG-RFP-2026-014. Our understanding is that "
            "Meridian Retail Group needs a single omnichannel service platform for 1,200 agents, growing to "
            "3,000, integrated with Salesforce CRM, SAP S/4HANA and Genesys, delivered with minimal disruption "
            "to store and online customers.",
            "Our proposal balances capability, cost and delivery certainty, and puts particular emphasis on a "
            "low-risk implementation and a strong long-term support model.",
        ],
        "solution": [
            "We propose a modular, cloud-hosted platform built on a service-oriented architecture with an API "
            "gateway and REST APIs. Core modules cover case management, omnichannel routing (voice, chat, "
            "email, WhatsApp), knowledge management and reporting.",
            "We provide connectors for Salesforce CRM and Genesys Cloud. SAP S/4HANA integration is delivered "
            "through SAP's standard OData services; an integration specification is produced in the design "
            "phase. The platform scales horizontally and supports 3,000 concurrent agents with autoscaling.",
        ],
        "implementation": [
            "Delivery follows a phased 20-week plan with 8 weeks of hypercare after go-live.",
            "Phase 1 Discovery (weeks 1-3): current-state assessment and requirements sign-off. Phase 2 Design "
            "(weeks 4-6): solution design and integration specification. Phase 3 Build (weeks 7-13) in two-week "
            "sprints with sprint demos. Phase 4 Test (weeks 14-17): system integration testing, performance "
            "testing and user acceptance testing (UAT). Phase 5 Pilot and Rollout (weeks 18-20): pilot with "
            "150 agents, then rollout in three waves.",
            "Milestones: M1 requirements sign-off (week 3), M2 design sign-off (week 6), M3 build complete "
            "(week 13), M4 UAT sign-off (week 17), M5 pilot go-live (week 18), M6 full go-live (week 20).",
            "Team structure: engagement director, delivery manager, solution architect, integration lead, five "
            "engineers, two QA engineers, a change manager and a trainer. A RACI matrix is included in Annex B.",
            "Risk management: a risk register with owners and mitigation actions is reviewed weekly. Top risks "
            "and mitigations: SAP data quality (mitigation: data profiling in Discovery), agent adoption "
            "(mitigation: pilot and train-the-trainer), peak-season freeze (mitigation: go-live scheduled "
            "before the festive code freeze). A rollback plan is defined for each rollout wave.",
        ],
        "price_rows": [
            ["Platform subscription (3 years, 1,200 agents)", "$540,000"],
            ["Implementation services (fixed price)", "$250,000"],
            ["Integration (Salesforce, SAP, Genesys)", "$60,000"],
            ["Training, change management and hypercare", "$40,000"],
            ["Total contract value (3 years)", "$890,000"],
        ],
        "assumptions": [
            "Prices exclude taxes. Implementation is a fixed price for the scope in Section 2; changes follow a "
            "change control process with a published day rate of $900. Subscription is billed annually. "
            "Payment milestones are tied to M2, M4 and M6. Total cost of ownership over three years is shown "
            "above with no hidden fees.",
        ],
        "security": [
            "NexaWorks is ISO/IEC 27001 certified and holds a SOC 2 Type I report; our SOC 2 Type II audit "
            "is in progress.",
            "Data is encrypted at rest (AES-256) and in transit (TLS 1.2+). Access uses SSO with SAML 2.0, "
            "role-based access control and multi-factor authentication. Audit logs are retained for 12 months.",
            "We comply with GDPR and the DPDP Act 2023 and host data in India. Penetration testing is carried "
            "out annually by an independent firm.",
        ],
        "support": [
            "Support is 24x7x365 with a tiered L1/L2/L3 model and a dedicated customer success manager.",
            "SLA response times: P1 15 minutes, P2 1 hour, P3 4 hours, P4 1 business day, with service credits "
            "if targets are missed. Quarterly service reviews and a shared knowledge base are included.",
            "Relevant experience: seven contact-centre implementations for retail and consumer brands since "
            "2019, including two with SAP S/4HANA integration.",
            "References: Lakeside Home Stores (VP Customer Experience), Crescent Fashion (CTO) and Pinecrest "
            "Grocers (Head of IT). Contact details are provided in Annex D.",
        ],
    },
    "Orbit Digital": {
        "file": "orbit_digital_proposal.pdf",
        "tagline": "18 years of customer experience excellence",
        "summary": [
            "Orbit Digital is delighted to respond to Meridian Retail Group's RFP. With 18 years of experience "
            "and more than 40 customer service platform implementations, we understand the challenges of "
            "modernising contact centres for large retailers.",
            "Our proposal draws on this experience to deliver a proven platform with dependable support.",
        ],
        "solution": [
            "We will deploy Orbit CX, our established customer service suite, covering case management, "
            "omnichannel routing and knowledge management. Orbit CX is cloud-hosted and has been load tested "
            "with 2,500 concurrent agents.",
            "Integration with Meridian's CRM, ERP and telephony systems will be finalised during discovery. "
            "We will use standard connectors as needed; the detailed integration approach is to be confirmed "
            "once we have reviewed Meridian's environment. The platform has supported large agent populations "
            "for other clients.",
        ],
        "implementation": [
            "We expect delivery to take approximately 22 weeks, structured as discovery (weeks 1-4), "
            "configuration (weeks 5-14), testing (weeks 15-19) and rollout (weeks 20-22).",
            "Milestones: design sign-off, UAT sign-off and go-live. Exact dates will be agreed after "
            "discovery.",
            "Our team will include a delivery manager, a solution architect and a team of consultants drawn "
            "from our delivery centre. A risk register will be maintained by the delivery manager, and our "
            "change management lead will support agent training.",
        ],
        "price_rows": [
            ["Orbit CX licences (3 years, 1,200 agents)", "$600,000"],
            ["Implementation services (fixed price)", "$260,000"],
            ["Training", "$30,000"],
            ["Integration (estimate, to be confirmed)", "$50,000"],
            ["Total contract value (3 years)", "$940,000"],
        ],
        "assumptions": [
            "Prices exclude taxes. Licences are billed annually. Implementation is fixed price for "
            "configuration; integration is an estimate and may change after discovery. Payment milestones "
            "are aligned to design sign-off, UAT sign-off and go-live.",
        ],
        "security": [
            "Orbit Digital is ISO/IEC 27001 certified. Data is encrypted at rest and in transit.",
            "Access is controlled through role-based access control and SSO. We comply with GDPR and will "
            "support Meridian's data protection obligations.",
        ],
        "support": [
            "Support is 24x7 with a tiered L1/L2/L3 model and a named account manager. SLA response times: "
            "P1 30 minutes, P2 2 hours, P3 1 business day.",
            "Relevant experience: more than 40 implementations since 2008, including 12 for retailers with "
            "over 1,000 agents.",
            "References: Silverline Department Stores (COO), Bayview Pharmacies (Head of Customer Care), "
            "Redwood Electronics (CIO) and Summit Travel (VP Operations). Contact details in Annex E.",
        ],
    },
}

# Tie-break fixture: Zenith is written to receive the same mock scores as Orbit Digital,
# so the two tie on PPI and absolute score and the deterministic tie-break order decides.
SUPPLIERS["Zenith Consulting"] = {
    **{k: v for k, v in SUPPLIERS["Orbit Digital"].items()},
    "file": "zenith_consulting_proposal.pdf",
    "tagline": "Experienced partners for customer experience",
    "summary": [
        "Zenith Consulting is delighted to respond to Meridian Retail Group's RFP. With 18 years of experience "
        "and more than 40 customer service platform implementations, we understand the challenges of "
        "modernising contact centres for large retailers.",
        "[Classroom note: this proposal intentionally mirrors Orbit Digital so that the two suppliers tie on "
        "score and the tie-break rules can be demonstrated.]",
    ],
    "support": [
        "Support is 24x7 with a tiered L1/L2/L3 model and a named account manager. SLA response times: "
        "P1 30 minutes, P2 2 hours, P3 1 business day.",
        "Relevant experience: more than 40 implementations since 2008, including 12 for retailers with "
        "over 1,000 agents.",
        "References: Maple Hardware (COO), Cedar Health Stores (Head of Customer Care), Granite Mobile (CIO) "
        "and Willow Hotels (VP Operations). Contact details in Annex E.",
    ],
}

SECTION_TITLES = [
    ("summary", "1. Executive Summary and Understanding of the Requirement"),
    ("solution", "2. Proposed Solution and Technical Approach"),
    ("implementation", "3. Implementation Approach, Timeline, Team and Milestones"),
    ("pricing", "4. Commercial Proposal"),
    ("security", "5. Security, Compliance and Risk Controls"),
    ("support", "6. Support Model, Relevant Experience and References"),
]


def _styles():
    ss = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("t", parent=ss["Title"], fontSize=22, leading=26, spaceAfter=6),
        "sub": ParagraphStyle("s", parent=ss["Normal"], alignment=TA_CENTER, textColor=colors.HexColor("#555555")),
        "h": ParagraphStyle("h", parent=ss["Heading2"], textColor=colors.HexColor("#0B3D5C"), spaceBefore=12),
        "p": ParagraphStyle("p", parent=ss["BodyText"], fontSize=10.5, leading=15, spaceAfter=7),
    }


def build_supplier_pdf(name: str, data: dict) -> Path:
    st = _styles()
    path = OUT / data["file"]
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=18 * mm, bottomMargin=18 * mm, title=f"{name} - RFP Response",
                            author=name)

    def footer(canvas, d):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(20 * mm, 10 * mm, f"{name} | Response to {RFP_REF} | Fictional document for training")
        canvas.drawRightString(190 * mm, 10 * mm, f"Page {d.page}")
        canvas.restoreState()

    flow = [
        Spacer(1, 30 * mm),
        Paragraph(name, st["title"]),
        Paragraph(data["tagline"], st["sub"]),
        Spacer(1, 10 * mm),
        Paragraph(f"Response to {RFP_REF}: {RFP_TITLE}", st["sub"]),
        Paragraph(f"Prepared for {BUYER}", st["sub"]),
        Spacer(1, 12 * mm),
    ]
    for key, title in SECTION_TITLES:
        flow.append(Paragraph(title, st["h"]))
        if key == "pricing":
            rows = [["Item", "Price (USD)"]] + data["price_rows"]
            t = Table(rows, colWidths=[120 * mm, 40 * mm])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B3D5C")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#BBBBBB")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#F2F6F9")]),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            flow += [t, Spacer(1, 5 * mm), Paragraph("<b>Pricing assumptions</b>", st["p"])]
            flow += [Paragraph(p, st["p"]) for p in data["assumptions"]]
        else:
            flow += [Paragraph(p, st["p"]) for p in data[key]]
        if key == "implementation":
            flow.append(PageBreak())
    doc.build(flow, onFirstPage=footer, onLaterPages=footer)
    return path


def build_edge_cases() -> list[Path]:
    """Files used to demonstrate validation / error handling."""
    EDGE.mkdir(parents=True, exist_ok=True)
    # 1) Not a PDF at all, just bytes with a .pdf extension.
    corrupt = EDGE / "corrupt_file.pdf"
    corrupt.write_bytes(b"This file is not really a PDF. It simulates a corrupted upload.\x00\x01\x02")
    # 2) A valid PDF that contains only graphics (simulates a scanned document without OCR).
    from reportlab.pdfgen import canvas as rl_canvas

    scanned = EDGE / "scanned_no_text.pdf"
    c = rl_canvas.Canvas(str(scanned), pagesize=A4)
    for i in range(18):
        c.setFillColor(colors.HexColor("#CCCCCC" if i % 2 else "#E5E5E5"))
        c.rect(25 * mm, (270 - i * 13) * mm, 160 * mm, 6 * mm, fill=1, stroke=0)
    c.showPage()
    c.save()
    return [corrupt, scanned]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, data in SUPPLIERS.items():
        print("created", build_supplier_pdf(name, data).relative_to(OUT.parent))
    for p in build_edge_cases():
        print("created", p.relative_to(OUT.parent))


if __name__ == "__main__":
    main()
