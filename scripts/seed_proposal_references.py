"""Explicit development-only seed for proposal reference search.

Run manually with: python scripts/seed_proposal_references.py
The seed is labelled SAMPLE_DATA and is never run by application startup.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.database import SessionLocal  # noqa: E402
from app.models import ProposalReference, ProposalReferenceDocument  # noqa: E402
from app.proposal_reference import normalize_title  # noqa: E402


SAMPLES = [
    ("Campus Safety Risk Mapping", "Maps student safety risks and proposes practical controls.", "Safety and campus operations"),
    ("Accessible Learning Resource Hub", "Improves access to course resources for diverse learners.", "Education technology and accessibility"),
    ("Smart Energy Monitoring for Labs", "Tracks laboratory energy use to support evidence-based reduction plans.", "Sustainability and IoT"),
    ("University Transport Route Planner", "Provides route information and demand insights for campus transport.", "Mobility and logistics"),
    ("Student Wellbeing Check-in Platform", "Supports confidential wellbeing check-ins and referral information.", "Student services"),
    ("Research Asset Inventory Portal", "Organizes shared research equipment and availability records.", "Research operations"),
    ("Secure Internship Tracking Workspace", "Maintains internship milestones and supervisor updates in one workspace.", "Career services"),
    ("Library Discovery Assistant", "Helps students locate library resources through deterministic metadata search.", "Knowledge services"),
]


def sample_pdf(title: str, summary: str) -> bytes:
    lines = [f"Proposal Title: {title}", f"Purpose: {summary}", "Source: SAMPLE_DATA"]
    content = "BT /F1 11 Tf 72 700 Td " + " ".join(f"({line.replace('(', '[').replace(')', ']')}) Tj 0 -20 Td" for line in lines) + " ET"
    content_bytes = content.encode("latin-1", errors="replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        f"<< /Length {len(content_bytes)} >>\nstream\n".encode() + content_bytes + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    result = b"%PDF-1.4\n"
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(result))
        result += f"{index} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(result)
    result += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    result += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
    result += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return result


def main() -> None:
    session = SessionLocal()
    try:
        created = 0
        for title, summary, category in SAMPLES:
            existing = session.query(ProposalReference).filter_by(title=title, source_label="SAMPLE_DATA").one_or_none()
            if existing is not None:
                continue
            data = sample_pdf(title, summary)
            reference = ProposalReference(title=title, normalized_title=normalize_title(title), short_summary=summary, academic_year="SAMPLE-2026", category_scope=category, source_label="SAMPLE_DATA", source_metadata={"fixture": "development-only", "sample": True})
            session.add(reference)
            session.flush()
            session.add(ProposalReferenceDocument(reference_id=reference.id, filename=f"sample-{reference.id}.pdf", content_type="application/pdf", file_size=len(data), sha256=hashlib.sha256(data).hexdigest(), content=data))
            created += 1
        session.commit()
        print(f"Created {created} SAMPLE_DATA proposal references; existing samples were left unchanged.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
