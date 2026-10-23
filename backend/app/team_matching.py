"""Opt-in, same-cycle matching of shared-team preferences."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from sqlalchemy import delete, or_, select, update as sql_update
from sqlalchemy.orm import Session
from .auth import get_current_user, utc_now, validate_mutating_origin
from .database import get_db
from .models import MatchChat, MatchConsent, Team, TeamPreference, User, UserRole, AnonymousIdentityProof
from .anonymous_verification import MatchingIdentityInput, get_context
from .individual_verification import eligible
from .security import hash_session_token
from .team_compatibility import aggregate_compatibility

router = APIRouter(prefix="/api/v1/team-matching")
GROUPS = {"skills": ("skills", "skills_wanted"), "domain": ("domain", "domain_interest"), "availability": ("availability",), "work_style": ("work_style",), "preferred_role": ("preferred_role",), "commitment": ("commitment",)}
class Preferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    skills: str = Field(default="", max_length=200, strict=True)
    skills_wanted: str = Field(default="", max_length=200, strict=True)
    domain: str = Field(default="", max_length=200, strict=True)
    domain_interest: str = Field(default="", max_length=200, strict=True)
    availability: str = Field(default="", max_length=200, strict=True)
    work_style: str = Field(default="", max_length=200, strict=True)
    preferred_role: str = Field(default="", max_length=200, strict=True)
    commitment: str = Field(default="", max_length=200, strict=True)
class PreferenceWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    opted_in: StrictBool
    answers: Preferences

def owned(session, actor):
    if actor.role != UserRole.STUDENT: raise HTTPException(403, "Team access is required.")
    team = session.scalar(select(Team).where(Team.shared_user_id == actor.id))
    if team is None: raise HTTPException(403, "Team access is required.")
    return team

def assessments(a, b):
    result = {}
    for category, keys in GROUPS.items():
        pairs = [(a.get(k, "").strip().casefold(), b.get(k, "").strip().casefold()) for k in keys]
        comparable = [(x, y) for x, y in pairs if x and y]
        result[category] = all(x == y for x, y in comparable) if comparable else None
    return result
@router.get("/preferences")
def read(actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    team = owned(session, actor); profile = session.get(TeamPreference, team.id)
    return {"opted_in": profile.opted_in, "answers": profile.answers} if profile else {"opted_in": False, "answers": Preferences().model_dump()}
@router.put("/preferences")
def update(payload: PreferenceWrite, request: Request, actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    try:
        team = owned(session, actor)
        session.execute(select(Team).where(Team.id == team.id).with_for_update()).scalar_one()
        profile = session.get(TeamPreference, team.id)
        if not profile: profile = TeamPreference(team_id=team.id); session.add(profile)
        profile.opted_in = payload.opted_in; profile.answers = payload.answers.model_dump()
        if not payload.opted_in:
            affected_chats = select(MatchChat.id).where(or_(MatchChat.team_a_id == team.id, MatchChat.team_b_id == team.id))
            session.execute(delete(MatchConsent).where(MatchConsent.closed_chat_id.in_(affected_chats)))
            session.execute(sql_update(MatchChat).where(MatchChat.closed_at.is_(None), or_(MatchChat.team_a_id == team.id, MatchChat.team_b_id == team.id)).values(closed_at=utc_now()))
        session.commit()
        return {"opted_in": profile.opted_in, "answers": profile.answers}
    except HTTPException:
        session.rollback(); raise
    except Exception:
        session.rollback(); raise HTTPException(500, "Preferences could not be saved.") from None
@router.get("/suggestions")
def suggestions(actor: User = Depends(get_current_user), session: Session = Depends(get_db)):
    team = owned(session, actor); profile = session.get(TeamPreference, team.id)
    if not profile or not profile.opted_in: return []
    candidates = session.execute(select(Team, TeamPreference).join(TeamPreference, TeamPreference.team_id == Team.id).where(Team.academic_cycle_id == team.academic_cycle_id, Team.id != team.id, TeamPreference.opted_in.is_(True))).all()
    output = []
    for candidate, preferences in candidates:
        result = aggregate_compatibility(assessments(profile.answers, preferences.answers))
        if result["answered"]: output.append({"team_id": candidate.id, **result})
    return sorted(output, key=lambda item: (-item["fraction"], item["team_id"]))


class StudentDiscovery(MatchingIdentityInput):
    proof: str = Field(min_length=1, max_length=256, strict=True)
    answers: Preferences

@router.post("/student-suggestions")
def student_suggestions(payload: StudentDiscovery, request: Request, session: Session = Depends(get_db)):
    validate_mutating_origin(request)
    try:
        context = get_context(session, request, lock=True)
        student = eligible(session, payload)
        if not student:
            raise HTTPException(400, "Discovery could not be completed.")
        now = utc_now()
        consumed = session.execute(sql_update(AnonymousIdentityProof).where(
            AnonymousIdentityProof.token_hash == hash_session_token(payload.proof),
            AnonymousIdentityProof.context_id == context.id,
            AnonymousIdentityProof.student_id == student.id,
            AnonymousIdentityProof.cycle_id == payload.cycle_id,
            AnonymousIdentityProof.purpose == 'student_matching',
            AnonymousIdentityProof.action == 'discover_groups',
            AnonymousIdentityProof.target_team_id.is_(None),
            AnonymousIdentityProof.expires_at > now,
            AnonymousIdentityProof.consumed_at.is_(None),
        ).values(consumed_at=now).returning(AnonymousIdentityProof.id)).scalar_one_or_none()
        if consumed is None:
            raise HTTPException(400, "Discovery could not be completed.")
        candidates = session.execute(select(Team, TeamPreference).join(TeamPreference, TeamPreference.team_id == Team.id).where(Team.academic_cycle_id == payload.cycle_id, TeamPreference.opted_in.is_(True))).all()
        results = []
        for team, preferences in candidates:
            comparison = aggregate_compatibility(assessments(payload.answers.model_dump(), preferences.answers))
            if comparison['answered']:
                results.append((comparison['fraction'], team.id, comparison['categories']))
        results.sort(key=lambda item: (-item[0], item[1]))
        session.commit()
        return [{'team_id': team_id, 'categories': categories} for _, team_id, categories in results]
    except HTTPException:
        session.rollback(); raise
    except Exception:
        session.rollback(); raise HTTPException(500, "Discovery could not be completed.") from None
