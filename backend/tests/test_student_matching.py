from unittest.mock import patch
from sqlalchemy import text
from tests.test_anonymous_verification import AnonymousVerificationTests
from tests.test_auth_sessions import request
from tests.test_team_matching import TeamMatchingTests

class StudentMatchingTests(AnonymousVerificationTests):
    def setup_matching(self):
        self.prepare()
        self.data = {"cycle_id": self.cycle.id, "registration_number": self.data["registration_number"], "university_email": self.data["university_email"], "purpose": "student_matching", "action": "discover_groups"}
        self.connection.execute(text("insert into team_match_preferences (team_id,opted_in,answers) values (:t,true,cast(:a as json))"), {"t": self.team_id, "a": '{"skills":"Python","domain":"Web"}'})
        cookie = self.context()
        with patch("app.anonymous_verification.send_email") as mail:
            self.assertEqual(self.call("challenge", self.data, cookie)[0], 200)
            code = mail.call_args.args[1]
        status, _, response = self.call("verify", {**self.data, "code": code}, cookie)
        self.assertEqual(status, 200)
        return cookie, response["proof"]

    def discover(self, cookie, proof, **overrides):
        data = {**self.data, "proof": proof, "answers": {"skills": " python ", "domain": "Mobile"}, **overrides}
        return request("POST", "/api/v1/team-matching/student-suggestions", data, headers={"cookie": cookie} if cookie else {})

    def test_comparison_privacy_and_replay(self):
        cookie, proof = self.setup_matching()
        self.assertEqual(self.discover(None, proof)[0], 400)
        self.assertEqual(self.discover(cookie, proof, cycle_id=self.cycle.id+999)[0], 400)
        self.assertEqual(self.discover(cookie, proof, university_email="wrong@example.com")[0], 400)
        status, _, result = self.discover(cookie, proof)
        self.assertEqual(status, 200)
        self.assertEqual(result, [{"team_id": self.team_id, "categories": {"skills": True, "domain": False}}])
        self.assertEqual(self.discover(cookie, proof)[0], 400)

    def test_opt_out(self):
        cookie, proof = self.setup_matching()
        self.connection.execute(text("update team_match_preferences set opted_in=false where team_id=:t"), {"t": self.team_id})
        self.assertEqual(self.discover(cookie, proof)[2], [])

    def test_unverified_and_wrong_purpose(self):
        cookie, proof = self.setup_matching()
        self.assertEqual(self.discover(cookie, "wrong")[0], 400)
        self.assertEqual(self.discover(cookie, proof, action="submit_join_request")[0], 422)
        self.assertEqual(self.discover(cookie, proof, answers={"private": "secret"})[0], 422)

    def test_cross_cycle_not_disclosed(self):
        cookie, proof = self.setup_matching()
        _, other = TeamMatchingTests.new_team(self, True)
        self.connection.execute(text("insert into team_match_preferences (team_id,opted_in,answers) values (:t,true,cast(:a as json))"), {"t": other, "a": '{"skills":"Python"}'})
        self.assertEqual([r["team_id"] for r in self.discover(cookie, proof)[2]], [self.team_id])

    def test_expired_proof(self):
        cookie, proof = self.setup_matching()
        self.connection.execute(text("update anonymous_identity_proofs set expires_at=now()-interval '1 second' where student_id=:s"), {"s": self.student_id})
        self.assertEqual(self.discover(cookie, proof)[0], 400)
