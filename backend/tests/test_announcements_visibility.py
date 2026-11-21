from datetime import datetime, timezone
from types import SimpleNamespace

from app.announcements import _visible
from app.models import UserRole


NOW = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)


def _admin(admin_id: int = 1):
    return SimpleNamespace(id=admin_id, role=UserRole.ADMIN)


def _student(student_id: int = 10):
    return SimpleNamespace(id=student_id, role=UserRole.STUDENT)


def _announcement(*, target_type: str, target_role: str | None = None, author_id: int = 99):
    return SimpleNamespace(
        id=1,
        author_id=author_id,
        author_role=UserRole.SUPERVISOR.value,
        target_type=target_type,
        target_role=target_role,
        status="PUBLISHED",
        published_at=NOW,
        expires_at=None,
    )


def test_admin_sees_platform_wide_announcements():
    assert _visible(_announcement(target_type="ALL_USERS"), _admin(), None, NOW) is True


def test_admin_sees_only_role_announcements_targeted_to_admins():
    assert _visible(_announcement(target_type="ROLE", target_role=UserRole.ADMIN.value), _admin(), None, NOW) is True
    assert _visible(_announcement(target_type="ROLE", target_role=UserRole.SUPERVISOR.value), _admin(), None, NOW) is False


def test_admin_does_not_see_private_group_announcements_even_when_authored_by_admin():
    row = _announcement(target_type="GROUP", author_id=1)
    assert _visible(row, _admin(), None, NOW) is False


def test_all_groups_announcement_is_only_visible_to_students():
    row = _announcement(target_type="ALL_GROUPS")
    assert _visible(row, _student(), None, NOW) is True
    assert _visible(row, _admin(), None, NOW) is False

