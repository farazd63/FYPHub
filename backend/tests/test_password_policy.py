import unittest

from pydantic import ValidationError

from app.schemas.admin_users import AdminUserCreate
from app.schemas.auth import RegistrationRequest
from app.security import password_policy_errors, validate_password


class PasswordPolicyTests(unittest.TestCase):
    def test_shared_policy_accepts_compliant_password(self) -> None:
        self.assertEqual(password_policy_errors("ValidPassword1!"), [])
        validate_password("ValidPassword1!")

    def test_shared_policy_reports_each_missing_requirement(self) -> None:
        errors = password_policy_errors("pass")
        self.assertIn("at least 8 characters", errors)
        self.assertIn("one uppercase letter", errors)
        self.assertIn("one number", errors)
        self.assertIn("one special character", errors)
        with self.assertRaisesRegex(ValueError, "one uppercase letter"):
            validate_password("pass")

    def test_shared_policy_rejects_overlong_values(self) -> None:
        self.assertIn("no more than 128 characters", password_policy_errors("A" * 129 + "a1!"))

    def test_student_and_admin_creation_schemas_use_shared_policy(self) -> None:
        registration = {
            "full_name": "Student",
            "email": "student@example.com",
            "registration_number": "STU-1",
            "password": "without-number",
        }
        with self.assertRaises(ValidationError):
            RegistrationRequest.model_validate(registration)
        with self.assertRaises(ValidationError):
            AdminUserCreate.model_validate({
                "full_name": "Supervisor",
                "email": "supervisor@example.com",
                "password": "WithoutNumber!",
                "role": "SUPERVISOR",
            })

    def test_admin_registration_number_is_role_dependent(self) -> None:
        supervisor = AdminUserCreate.model_validate({
            "full_name": "Supervisor",
            "email": "supervisor@example.com",
            "password": "ValidPass123!",
            "role": "SUPERVISOR",
        })
        self.assertIsNone(supervisor.registration_number)
        with self.assertRaisesRegex(ValidationError, "registration_number is required"):
            AdminUserCreate.model_validate({
                "full_name": "Student",
                "email": "student@example.com",
                "password": "ValidPass123!",
                "role": "STUDENT",
            })


if __name__ == "__main__":
    unittest.main()
