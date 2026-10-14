"""Configure the approved local Fall 2026 academic-cycle bootstrap.

Run from the project root with:
    & '.\\backend\\.venv\\Scripts\\python.exe' .\\scripts\\configure_p1_cycle.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import select, text


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import SessionLocal  # noqa: E402
from app.models import AcademicCycle, AcademicGroupPolicy  # noqa: E402


CYCLE_CODE = "FALL-2026"
DISPLAY_NAME = "Fall 2026"
MAX_GROUP_SIZE = 3
REGISTRATION_OPEN = True
EXPECTED_DATABASE = "fyphub_p1"


def main() -> None:
    """Create the approved local setting, or verify it already matches exactly."""
    with SessionLocal.begin() as session:
        database_name = session.execute(text("SELECT current_database()")).scalar_one()
        if database_name != EXPECTED_DATABASE:
            raise RuntimeError(
                "Refusing to configure an unexpected database. "
                f"Expected {EXPECTED_DATABASE!r}, received {database_name!r}."
            )

        cycle = session.execute(
            select(AcademicCycle)
            .where(AcademicCycle.code == CYCLE_CODE)
            .with_for_update()
        ).scalar_one_or_none()

        created_cycle = cycle is None
        if cycle is None:
            cycle = AcademicCycle(
                code=CYCLE_CODE,
                display_name=DISPLAY_NAME,
                registration_open=REGISTRATION_OPEN,
            )
            session.add(cycle)
            session.flush()
        elif (
            cycle.display_name != DISPLAY_NAME
            or cycle.registration_open != REGISTRATION_OPEN
        ):
            raise RuntimeError(
                "Existing FALL-2026 cycle settings do not match the approved local configuration. "
                "No changes were made."
            )

        policy = session.execute(
            select(AcademicGroupPolicy)
            .where(AcademicGroupPolicy.academic_cycle_id == cycle.id)
            .with_for_update()
        ).scalar_one_or_none()

        created_policy = policy is None
        if policy is None:
            policy = AcademicGroupPolicy(
                academic_cycle_id=cycle.id,
                max_group_size=MAX_GROUP_SIZE,
            )
            session.add(policy)
            session.flush()
        elif policy.max_group_size != MAX_GROUP_SIZE:
            raise RuntimeError(
                "Existing FALL-2026 group policy does not match the approved local configuration. "
                "No changes were made."
            )

        result = {
            "cycle_id": cycle.id,
            "code": cycle.code,
            "display_name": cycle.display_name,
            "registration_open": cycle.registration_open,
            "max_group_size": policy.max_group_size,
            "cycle_created": created_cycle,
            "policy_created": created_policy,
        }

    print(
        "Configured local academic cycle: "
        f"id={result['cycle_id']}, code={result['code']}, "
        f"display_name={result['display_name']}, "
        f"registration_open={str(result['registration_open']).lower()}, "
        f"max_group_size={result['max_group_size']}, "
        f"cycle_created={str(result['cycle_created']).lower()}, "
        f"policy_created={str(result['policy_created']).lower()}"
    )


if __name__ == "__main__":
    main()
