import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import HTTPException
from pydantic import ValidationError
from starlette.requests import Request

from app.schemas.academic import CycleCreate, CycleUpdate
from app.supervisor_requests import _cycle_for_request
from app.main import update_cycle


class CycleMetadataSafetyTests(unittest.TestCase):
    def test_closed_registration_blocks_new_requests_but_allows_pending_review(self):
        db = Mock()
        cycle = SimpleNamespace(academic_year=2025, session="SPRING", registration_open=False)
        db.execute.return_value.scalar_one_or_none.return_value = cycle
        with self.assertRaises(HTTPException) as error:
            _cycle_for_request(db, 1)
        self.assertEqual(error.exception.detail["code"], "academic_cycle_closed")
        self.assertIs(_cycle_for_request(db, 1, require_open=False), cycle)

    def test_new_cycle_and_explicit_clearing_require_valid_period(self):
        for values in ({}, {"academic_year": 2025}, {"session": "SPRING"}):
            with self.assertRaises(ValidationError):
                CycleCreate(**values)
        for values in ({"academic_year": None}, {"session": None}, {"session": "SUMMER"}, {"academic_year": 1800}):
            with self.assertRaises(ValidationError):
                CycleUpdate(**values)
        self.assertEqual(CycleUpdate(academic_year=2025, session="spring").session.value, "SPRING")

    def test_incomplete_cycle_is_rejected_before_supervisor_request_processing(self):
        db = Mock()
        db.execute.return_value.scalar_one_or_none.return_value = SimpleNamespace(academic_year=None, session=None, registration_open=True)
        with self.assertRaises(HTTPException) as error:
            _cycle_for_request(db, 1)
        self.assertEqual(error.exception.status_code, 422)
        self.assertEqual(error.exception.detail["code"], "academic_cycle_metadata_missing")

    def test_registration_cannot_open_for_incomplete_legacy_cycle(self):
        cycle = SimpleNamespace(academic_year=None, session=None)
        request = Request({"type": "http", "method": "PATCH", "path": "/", "headers": []})
        db = Mock()
        with patch("app.main.locked_cycle_and_policy", return_value=(cycle, object())):
            with self.assertRaises(HTTPException) as error:
                update_cycle(1, CycleUpdate(registration_open=True), request, SimpleNamespace(id=1), db)
        self.assertEqual(error.exception.status_code, 422)
        db.commit.assert_not_called()

    def test_admin_can_repair_missing_year_and_session_together(self):
        cycle = SimpleNamespace(id=1, academic_year=None, session=None)
        request = Request({"type": "http", "method": "PATCH", "path": "/", "headers": []})
        db = Mock()
        with patch("app.main.locked_cycle_and_policy", return_value=(cycle, None)), patch("app.main.add_admin_audit_event"):
            result = update_cycle(1, CycleUpdate(academic_year=2025, session="SPRING"), request, SimpleNamespace(id=1), db)
        self.assertEqual((result.academic_year, result.session), (2025, "SPRING"))
        db.commit.assert_called_once()
