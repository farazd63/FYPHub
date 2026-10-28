"""Development-only idempotent archive fixtures; never run at application startup."""

import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.archived_projects import normalize_title
from app.database import SessionLocal
from app.models import ArchivedProject, ArchivedProjectDocument, User, UserRole

SAMPLES = [
    ("Campus Safety Risk Mapping", "Maps campus safety risks and proposes practical controls.", ["safety", "mapping", "campus"], "Safety and operations"),
    ("Accessible Learning Resource Hub", "Improves access to course resources for diverse learners.", ["accessibility", "education", "resources"], "Education technology"),
    ("Smart Energy Monitoring for Labs", "Tracks laboratory energy use to support evidence-based reduction plans.", ["energy", "iot", "sustainability"], "Sustainability and IoT"),
    ("University Transport Route Planner", "Provides route information and demand insights for campus transport.", ["transport", "routes", "planning"], "Mobility and logistics"),
    ("Student Wellbeing Check-in Platform", "Supports confidential wellbeing check-ins and referral information.", ["wellbeing", "student services", "privacy"], "Student services"),
    ("Research Asset Inventory Portal", "Organizes shared research equipment and availability records.", ["research", "inventory", "equipment"], "Research operations"),
    ("Secure Internship Tracking Workspace", "Maintains internship milestones and supervisor updates in one workspace.", ["internship", "tracking", "career"], "Career services"),
    ("Library Discovery Assistant", "Helps students locate library resources through deterministic metadata search.", ["library", "search", "metadata"], "Knowledge services"),
]


def sample_pdf(title: str, summary: str, document_type: str) -> bytes:
    text = f"FYPHub SAMPLE_DATA\n{document_type}\nTitle: {title}\nSummary: {summary}"
    stream = f"BT /F1 11 Tf 72 700 Td ({text.replace('(', '[').replace(')', ']')}) Tj ET".encode("latin-1", errors="replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    result = b"%PDF-1.4\n"; offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(result)); result += f"{index} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(result); result += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    result += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
    return result + f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()


def main() -> None:
    session = SessionLocal()
    try:
        admin = session.query(User).filter(User.role == UserRole.ADMIN, User.is_active.is_(True)).order_by(User.id).first()
        if admin is None:
            raise RuntimeError("Create a development Admin account before seeding archive fixtures.")
        created = 0
        for title, summary, keywords, scope in SAMPLES:
            project = session.query(ArchivedProject).filter_by(title=title, academic_year="SAMPLE-2026", source_label="SAMPLE_DATA").one_or_none()
            if project is None:
                project = ArchivedProject(title=title, normalized_title=normalize_title(title), abstract_summary=summary, keywords=keywords, academic_year="SAMPLE-2026", department_program="SAMPLE_DATA", project_scope=scope, completion_stage="Completed reference", implemented_scope=summary, remaining_gaps="SAMPLE_DATA limitations only.", future_work="SAMPLE_DATA future work.", source_label="SAMPLE_DATA", source_metadata={"fixture": "development-only"}, is_active=True)
                session.add(project); session.flush(); created += 1
            for document_type in ("SHORT_PROPOSAL", "LONG_PROPOSAL", "FINAL_REPORT"):
                if session.query(ArchivedProjectDocument).filter_by(archived_project_id=project.id, document_type=document_type, version=1).one_or_none():
                    continue
                content = sample_pdf(title, summary, document_type)
                session.add(ArchivedProjectDocument(archived_project_id=project.id, document_type=document_type, display_name=f"{document_type.lower()}-sample.pdf", storage_key=f"archive/{project.id}/{document_type.lower()}/v1-sample.pdf", file_hash=hashlib.sha256(content).hexdigest(), mime_type="application/pdf", file_size=len(content), content=content, version=1, uploaded_by_id=admin.id, is_active=True))
        session.commit(); print(f"Created {created} SAMPLE_DATA archived projects; existing fixtures were left unchanged.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
