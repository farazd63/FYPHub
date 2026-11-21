"""Idempotently seed three local supervisor accounts for matching demos."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, select

from app.database import SessionLocal
from app.models import (
    AcademicCycle,
    Institution,
    InstitutionDomain,
    InstitutionMembership,
    SupervisorAvailability,
    SupervisorCapacityPolicy,
    SupervisorExpertise,
    SupervisorProfile,
    SupervisorResearchInterest,
    SupervisorSkill,
    SupervisedProjectHistory,
    User,
    UserRole,
)
from app.security import hash_password


SEEDS = (
    {
        "name": "Muhammad Imran",
        "email": "muhammad.imran@szabist-isb.pk",
        "password": "Muhammad@01",
        "department": "Computer Science",
        "program": "Artificial Intelligence",
        "designation": "Assistant Professor",
        "degree": "PhD in Artificial Intelligence",
        "specialization": "Machine Learning and Intelligent Systems",
        "biography": "Works on practical AI systems that turn research prototypes into reliable student and industry solutions.",
        "expertise": ["Machine learning", "Natural language processing", "Deep learning", "Computer vision"],
        "skills": ["Python", "PyTorch", "TensorFlow", "NLP", "Model evaluation"],
        "interests": ["Responsible AI", "Generative AI", "Information retrieval", "Educational technology"],
        "publications": [
            "Transformer-based document classification for academic knowledge bases",
            "Explainable machine learning for student performance prediction",
        ],
        "projects": [
            ("Campus Knowledge Assistant", "AI assistant for searching university project documents.", ["Artificial Intelligence", "NLP"], ["Python", "RAG", "PostgreSQL"]),
            ("Explainable Student Risk Model", "An interpretable model for early academic support decisions.", ["Machine Learning", "Responsible AI"], ["Python", "PyTorch"]),
        ],
        "capacity": 5,
    },
    {
        "name": "Saad Irfan",
        "email": "saad.irfan@szabist-isb.pk",
        "password": "Saad@01",
        "department": "Computer Science",
        "program": "Software Engineering",
        "designation": "Assistant Professor",
        "degree": "PhD in Software Engineering",
        "specialization": "Software Architecture and Cloud Engineering",
        "biography": "Focuses on maintainable software delivery, quality engineering, and scalable cloud-native applications.",
        "expertise": ["Software architecture", "Requirements engineering", "Software testing", "DevOps"],
        "skills": ["Java", "TypeScript", "Docker", "Kubernetes", "CI/CD", "Agile delivery"],
        "interests": ["Cloud-native systems", "Software quality", "Distributed applications", "Developer productivity"],
        "publications": [
            "Continuous quality practices for student software projects",
            "A reference architecture for maintainable cloud-native services",
        ],
        "projects": [
            ("FYP Delivery Quality Platform", "A software engineering workflow for tracking quality gates and releases.", ["Software Engineering", "DevOps"], ["TypeScript", "Docker", "CI/CD"]),
            ("Service Reliability Observatory", "Observability and testing patterns for distributed student applications.", ["Software Testing", "Cloud"], ["Kubernetes", "Java"]),
        ],
        "capacity": 4,
    },
    {
        "name": "Muslim Rizwi",
        "email": "muslim.rizwi@szabist-isb.pk",
        "legacy_email": "muslim@szabist-isb.pk",
        "password": "Muslim@01",
        "department": "Computer Science",
        "program": "Computer Science",
        "designation": "Assistant Professor",
        "degree": "PhD in Computer Science",
        "specialization": "Data Systems and Cybersecurity",
        "biography": "Teaches and researches dependable data systems, algorithms, and secure computing for real-world applications.",
        "expertise": ["Algorithms", "Database systems", "Distributed systems", "Cybersecurity"],
        "skills": ["PostgreSQL", "SQL", "Java", "Data structures", "Network security", "System design"],
        "interests": ["Secure software systems", "Data engineering", "Privacy-preserving analytics", "Distributed computing"],
        "publications": [
            "Secure data pipelines for privacy-aware analytics",
            "Benchmarking distributed database workloads in resource-constrained environments",
        ],
        "projects": [
            ("Privacy-Aware FYP Data Hub", "A permission-aware platform for project documents and semantic search.", ["Data Engineering", "Cybersecurity"], ["PostgreSQL", "pgvector", "Python"]),
            ("Distributed Queue Benchmark", "An experimental comparison of reliable message processing strategies.", ["Distributed Systems", "Algorithms"], ["Java", "System design"]),
        ],
        "capacity": 5,
    },
)


def _upsert_child_rows(session, model, profile_id: int, values: list[dict]) -> None:
    existing = {row.name: row for row in session.scalars(select(model).where(model.profile_id == profile_id)).all()}
    wanted = set()
    for value in values:
        wanted.add(value["name"])
        row = existing.get(value["name"])
        if row is None:
            row = model(profile_id=profile_id, **value)
            session.add(row)
        else:
            for key, item in value.items():
                setattr(row, key, item)
            row.active = True
    for name, row in existing.items():
        if name not in wanted:
            row.active = False


def _upsert_history(session, profile_id: int, start_id: int, projects: list[tuple]) -> None:
    for offset, (title, abstract, domains, technologies) in enumerate(projects):
        source_id = start_id + offset
        row = session.scalar(
            select(SupervisedProjectHistory).where(
                SupervisedProjectHistory.profile_id == profile_id,
                SupervisedProjectHistory.source_type == "ARCHIVED_PROJECT",
                SupervisedProjectHistory.source_id == source_id,
            )
        )
        values = {
            "project_title": title,
            "abstract": abstract,
            "research_domain": domains,
            "problem_area": abstract,
            "methodology": "Iterative design, implementation, testing, and evaluation",
            "technologies": technologies,
            "keywords": domains + technologies,
            "year": 2025 + offset,
            "supervisor_role": "Supervisor",
            "project_status": "COMPLETED",
            "public_summary": abstract,
            "source_type": "ARCHIVED_PROJECT",
            "source_id": source_id,
            "source_verified": True,
        }
        if row is None:
            session.add(SupervisedProjectHistory(profile_id=profile_id, **values))
        else:
            for key, value in values.items():
                setattr(row, key, value)


def main() -> None:
    now = datetime.now(timezone.utc)
    with SessionLocal() as session:
        institution = session.scalar(
            select(Institution)
            .join(InstitutionDomain, InstitutionDomain.institution_id == Institution.id)
            .where(InstitutionDomain.domain == "szabist-isb.pk", InstitutionDomain.is_verified.is_(True), InstitutionDomain.is_active.is_(True))
        ) or session.scalar(select(Institution).where(Institution.slug == "legacy-default"))
        cycle = session.scalar(select(AcademicCycle).where(AcademicCycle.registration_open.is_(True)).order_by(AcademicCycle.id.desc()).limit(1))
        admin = session.scalar(select(User).where(User.role == UserRole.ADMIN).order_by(User.id).limit(1))
        if institution is None or cycle is None or admin is None:
            raise RuntimeError("An active institution, registration-open academic cycle, and admin account are required.")

        session.info["institution_id"] = institution.id
        session.info["platform_admin"] = True
        created: list[str] = []

        for index, seed in enumerate(SEEDS, start=1):
            user = session.scalar(select(User).where(User.email == seed["email"]))
            if user is None and seed.get("legacy_email"):
                user = session.scalar(select(User).where(User.email == seed["legacy_email"], User.role == UserRole.SUPERVISOR))
            if user is None:
                user = User(full_name=seed["name"], email=seed["email"], registration_number=None, password_hash=hash_password(seed["password"],), role=UserRole.SUPERVISOR)
                session.add(user)
                session.flush()
                created.append(seed["name"])

            user.full_name = seed["name"]
            user.email = seed["email"]
            user.password_hash = hash_password(seed["password"])
            user.role = UserRole.SUPERVISOR
            user.is_active = True
            user.institution_id = institution.id
            user.email_verified_at = now
            user.access_approved_at = now

            membership = session.scalar(select(InstitutionMembership).where(InstitutionMembership.institution_id == institution.id, InstitutionMembership.user_id == user.id))
            if membership is None:
                membership = InstitutionMembership(institution_id=institution.id, user_id=user.id, membership_role="MEMBER")
                session.add(membership)
            membership.status = "ACTIVE"
            membership.approved_by_id = admin.id
            membership.approved_at = now

            profile = session.scalar(select(SupervisorProfile).where(SupervisorProfile.supervisor_id == user.id))
            if profile is None:
                profile = SupervisorProfile(supervisor_id=user.id)
                session.add(profile)
                session.flush()
            profile.institution_id = institution.id
            profile.department = seed["department"]
            profile.program = seed["program"]
            profile.designation = seed["designation"]
            profile.degree = seed["degree"]
            profile.specialization = seed["specialization"]
            profile.biography = seed["biography"]
            profile.preferred_categories = seed["interests"][:2]
            profile.publications = [{"name": item, "evidence": "Seeded current relevant publication/project", "confidence": 1, "verified": True} for item in seed["publications"]]
            profile.profile_status = "VERIFIED"
            profile.visibility_status = "PUBLIC"
            profile.is_active = True
            profile.profile_version = max(profile.profile_version, 1)

            _upsert_child_rows(session, SupervisorExpertise, profile.id, [{"name": item, "evidence": "Current supervisor profile", "confidence": 1, "verified": True, "active": True} for item in seed["expertise"]])
            _upsert_child_rows(session, SupervisorSkill, profile.id, [{"category": "technical", "name": item, "evidence": "Current supervisor profile", "confidence": 1, "verified": True, "active": True} for item in seed["skills"]])
            _upsert_child_rows(session, SupervisorResearchInterest, profile.id, [{"name": item, "evidence": "Current supervisor profile", "confidence": 1, "verified": True, "active": True} for item in seed["interests"]])
            _upsert_history(session, profile.id, 910000 + index * 10, seed["projects"])

            availability = session.scalar(select(SupervisorAvailability).where(SupervisorAvailability.profile_id == profile.id, SupervisorAvailability.academic_cycle_id == cycle.id))
            if availability is None:
                availability = SupervisorAvailability(profile_id=profile.id, academic_cycle_id=cycle.id)
                session.add(availability)
            availability.institution_id = institution.id
            availability.available = True
            availability.maximum_capacity = seed["capacity"]
            availability.current_active_count = 0

            policy = session.scalar(select(SupervisorCapacityPolicy).where(SupervisorCapacityPolicy.supervisor_id == user.id, SupervisorCapacityPolicy.academic_year == cycle.academic_year))
            if policy is None:
                policy = SupervisorCapacityPolicy(supervisor_id=user.id, academic_cycle_id=cycle.id, academic_year=cycle.academic_year, max_group_capacity=seed["capacity"])
                session.add(policy)
            policy.institution_id = institution.id
            policy.academic_cycle_id = cycle.id
            policy.academic_year = cycle.academic_year
            policy.max_group_capacity = seed["capacity"]

        session.commit()
        print(f"Seeded {len(SEEDS)} supervisors for {institution.name} / {cycle.display_name}: {', '.join(seed['name'] for seed in SEEDS)}")
        print(f"Created new accounts: {', '.join(created) if created else 'none (already existed)'}")


if __name__ == "__main__":
    main()
