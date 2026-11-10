from datetime import datetime, timezone
from types import SimpleNamespace

from app.document_requirements import _visible, student_requirements
from app.models import UserRole


class _Rows:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class _Db:
    def __init__(self, rows):
        self.rows = rows

    def scalars(self, _statement):
        return _Rows(self.rows)


def _student(student_id=10):
    return SimpleNamespace(id=student_id, role=UserRole.STUDENT, registration_number=f"STUDENT-{student_id}", email=f"student-{student_id}@example.com")


def _requirement(title, *, status="ACTIVE", assigned_user_id=None, assigned_group_id=None, cycle_id=7):
    return SimpleNamespace(
        id=1, title=title, description=None, academic_cycle_id=cycle_id, module="General", visible_to_roles=["STUDENT"],
        assigned_user_id=assigned_user_id, assigned_group_id=assigned_group_id, allowed_file_types=["pdf"], max_file_size_mb=10,
        due_at=datetime(2026, 12, 1, tzinfo=timezone.utc), reminder_days_before=3, is_required=True,
        status=status, late_upload_allowed=False, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )


def test_published_all_students_requirement_appears(monkeypatch):
    student = _student()
    row = _requirement("All students")
    monkeypatch.setattr("app.document_requirements._student_cycle_ids", lambda _user, _db: {7})
    assert [item.title for item in student_requirements(student, _Db([row]))] == ["All students"]


def test_student_specific_requirement_appears_only_for_that_student(monkeypatch):
    row = _requirement("Specific", assigned_user_id=10)
    monkeypatch.setattr("app.document_requirements._student_cycle_ids", lambda _user, _db: {7})
    assert _visible(row, _student(10), _Db([])) is True
    assert _visible(row, _student(11), _Db([])) is False


def test_draft_and_archived_requirements_stay_hidden(monkeypatch):
    student = _student()
    monkeypatch.setattr("app.document_requirements._student_cycle_ids", lambda _user, _db: {7})
    rows = [_requirement("Draft", status="DRAFT"), _requirement("Archived", status="ARCHIVED"), _requirement("Published")]
    assert [item.title for item in student_requirements(student, _Db(rows))] == ["Published"]


def test_requirement_for_another_student_stays_hidden(monkeypatch):
    student = _student(10)
    row = _requirement("Another student", assigned_user_id=11)
    monkeypatch.setattr("app.document_requirements._student_cycle_ids", lambda _user, _db: {7})
    assert student_requirements(student, _Db([row])) == []
