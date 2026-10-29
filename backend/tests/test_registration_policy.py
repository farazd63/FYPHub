"""Unit coverage for the reversible registration-mode policy."""

import os
import unittest
from unittest.mock import patch

from app.registration_policy import DEMO_MODE_WARNING, RegistrationMode, get_registration_mode, registration_mode, roster_validation_required


class RegistrationPolicyTests(unittest.TestCase):
    def test_explicit_modes_and_fail_closed_defaults(self) -> None:
        self.assertEqual(get_registration_mode("demo"), RegistrationMode.DEMO)
        self.assertEqual(get_registration_mode(" DEMO "), RegistrationMode.DEMO)
        for value in (None, "", "invalid", "production"):
            with self.subTest(value=value):
                self.assertEqual(get_registration_mode(value), RegistrationMode.RESTRICTED)

    def test_environment_mode_and_roster_requirement(self) -> None:
        with patch.dict(os.environ, {"REGISTRATION_MODE": "demo"}):
            self.assertEqual(registration_mode(), RegistrationMode.DEMO)
            self.assertFalse(roster_validation_required())
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(registration_mode(), RegistrationMode.RESTRICTED)
            self.assertTrue(roster_validation_required())

    def test_admin_warning_is_exact_and_safe(self) -> None:
        self.assertEqual(DEMO_MODE_WARNING, "Demo registration mode is active. Approved roster validation is temporarily bypassed.")

