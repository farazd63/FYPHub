"""Focused assertions for the retired registry/roster/identity surface."""

from app.main import app


def test_retired_api_routes_are_not_registered():
    paths = app.openapi()["paths"]
    assert not [
        path
        for path in paths
        if any(
            marker in path
            for marker in (
                "fyp-registry",
                "student-roster",
                "workflow-policies",
                "invitations",
                "join-requests",
                "verification",
                "team-matching",
            )
        )
    ]
