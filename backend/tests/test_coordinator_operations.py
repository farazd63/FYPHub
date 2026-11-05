from app.coordinator_operations import router
from app.main import app


def test_coordinator_read_only_routes_are_registered():
    paths = app.openapi()["paths"]
    assert "/api/v1/coordinator/supervisor-capacity" in paths
    assert "/api/v1/coordinator/audit-history" in paths
    assert {route.path for route in router.routes} == {
        "/api/v1/coordinator/supervisor-capacity",
        "/api/v1/coordinator/audit-history",
        "/api/v1/coordinator/workflow-policies",
        "/api/v1/coordinator/proposal-templates",
        "/api/v1/coordinator/evaluation-criteria",
    }


def test_coordinator_operations_are_read_only_get_routes():
    assert all(route.methods == {"GET"} for route in router.routes)
