"""Isolated checks for the non-operational proposal schema."""
import unittest
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import IntegrityError
from app.models.proposal import Proposal, ProposalVersion

class ProposalFoundationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
        with self.engine.begin() as connection:
            connection.execute(text("CREATE TABLE teams (id INTEGER PRIMARY KEY)"))
            connection.execute(text("INSERT INTO teams (id) VALUES (1)"))
            Proposal.__table__.create(connection)
            ProposalVersion.__table__.create(connection)

    def tearDown(self):
        self.engine.dispose()

    def test_short_long_and_independent_version_sequences(self):
        with self.engine.begin() as connection:
            connection.execute(Proposal.__table__.insert(), [{"id": 1, "team_id": 1, "proposal_type": "SHORT"}, {"id": 2, "team_id": 1, "proposal_type": "LONG"}])
            connection.execute(ProposalVersion.__table__.insert(), [{"proposal_id": 1, "version_number": 1}, {"proposal_id": 1, "version_number": 2}, {"proposal_id": 2, "version_number": 1}])
            self.assertEqual(connection.scalar(text("SELECT count(*) FROM proposal_versions")), 3)

    def test_invalid_type_and_missing_team_are_rejected(self):
        for payload in ({"team_id": 1, "proposal_type": "OTHER"}, {"team_id": 99, "proposal_type": "SHORT"}):
            with self.subTest(payload=payload), self.assertRaises(IntegrityError), self.engine.begin() as connection:
                connection.execute(Proposal.__table__.insert(), payload)

    def test_invalid_version_duplicate_and_missing_parent_are_rejected(self):
        with self.engine.begin() as connection:
            connection.execute(Proposal.__table__.insert(), {"id": 1, "team_id": 1, "proposal_type": "SHORT"})
            connection.execute(ProposalVersion.__table__.insert(), {"proposal_id": 1, "version_number": 1})
        for payload in ({"proposal_id": 1, "version_number": 1}, {"proposal_id": 1, "version_number": 0}, {"proposal_id": 99, "version_number": 1}):
            with self.subTest(payload=payload), self.assertRaises(IntegrityError), self.engine.begin() as connection:
                connection.execute(ProposalVersion.__table__.insert(), payload)

    def test_no_operational_proposal_routes(self):
        from app.main import app
        self.assertFalse(any(path.startswith("/api/v1/proposals") for path in app.openapi()["paths"]))

