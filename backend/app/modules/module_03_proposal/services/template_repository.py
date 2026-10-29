"""Small repository helpers used by routes and tests."""

import hashlib
import json
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..models import M03ReferenceTemplate, M03TemplateRule


def active_template(session: Session, template_type: str) -> M03ReferenceTemplate | None:
    return session.scalar(select(M03ReferenceTemplate).where(M03ReferenceTemplate.template_type == template_type, M03ReferenceTemplate.is_active.is_(True)).order_by(M03ReferenceTemplate.version.desc()))


def next_template_version(session: Session, template_type: str) -> int:
    return int(session.scalar(select(func.max(M03ReferenceTemplate.version)).where(M03ReferenceTemplate.template_type == template_type)) or 0) + 1


def rule_content_hash(rules: dict) -> str:
    return hashlib.sha256(json.dumps(rules, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def latest_rule_version(session: Session, template_id: int) -> int:
    return int(session.scalar(select(func.max(M03TemplateRule.rule_version)).where(M03TemplateRule.reference_template_id == template_id)) or 0)


def save_rules(session: Session, template: M03ReferenceTemplate, *, rule_version: int | None = None, provenance: str = "Observed reference property", confirm_duplicate: bool = False) -> tuple[int, bool]:
    content_hash = rule_content_hash(template.extracted_rules)
    latest = latest_rule_version(session, template.id)
    if latest and not confirm_duplicate:
        existing = session.scalar(select(M03TemplateRule.id).where(M03TemplateRule.reference_template_id == template.id, M03TemplateRule.rule_version == latest, M03TemplateRule.content_hash == content_hash))
        if existing is not None:
            return latest, False
    version = rule_version or latest + 1
    for key, value in template.extracted_rules.items():
        session.add(M03TemplateRule(reference_template_id=template.id, rule_key=key, rule_value={"value": value}, rule_version=version, content_hash=content_hash, source="deterministic document extraction", provenance=provenance, confidence=template.confidence or "UNKNOWN"))
    return version, True
