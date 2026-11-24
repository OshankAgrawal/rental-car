import os
import unittest
from unittest.mock import patch

from services.auth_service import (
    AuthConfigurationError,
    create_session_token,
    get_auth_settings,
    validate_session_token,
)


class AuthServiceTests(unittest.TestCase):
    def test_signed_session_token_expires_and_rejects_tampering(self):
        secret = "a-session-signing-secret-with-more-than-32-characters"
        token = create_session_token("friend", secret, now=100)

        self.assertTrue(validate_session_token(token, "friend", secret, now=101))
        self.assertFalse(validate_session_token(token, "friend", secret, now=100 + 8 * 60 * 60))
        self.assertFalse(validate_session_token(token + "bad", "friend", secret, now=101))

    def test_example_credentials_are_rejected(self):
        with patch.dict(os.environ, {
            "APP_USERNAME": "friend",
            "APP_PASSWORD": "change-this-to-a-long-unique-password",
            "APP_SESSION_SECRET": "replace-with-a-random-secret-at-least-32-characters",
        }):
            with self.assertRaises(AuthConfigurationError):
                get_auth_settings()


if __name__ == "__main__":
    unittest.main()
