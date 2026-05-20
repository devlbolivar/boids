"""
conftest.py for unit tests.

Mocks heavy optional dependencies (google-auth, google-api-python-client)
so they don't need to be installed in the local dev environment.
The mocks are registered in sys.modules before any test imports run.
"""
import sys
from unittest.mock import MagicMock

# ── google-auth / google-api-python-client stubs ──────────────────────────────
# Only install if the real packages aren't present.
_GOOGLE_MODULES = [
    "google",
    "google.oauth2",
    "google.oauth2.credentials",
    "google.auth",
    "google.auth.transport",
    "google.auth.transport.requests",
    "googleapiclient",
    "googleapiclient.discovery",
]

for _mod in _GOOGLE_MODULES:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

# Ensure Credentials is accessible as a class mock
if not hasattr(sys.modules["google.oauth2.credentials"], "Credentials"):
    sys.modules["google.oauth2.credentials"].Credentials = MagicMock()
