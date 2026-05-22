"""
tests/conftest.py — Shared pytest fixtures for Signal Brain tests.

Sets required environment variables before any test module imports config,
preventing KeyError on ALPACA_API_KEY / ALPACA_SECRET_KEY during offline tests.
"""

import os

# Set before config is imported by any test module.
os.environ.setdefault("ALPACA_API_KEY", "test_api_key")
os.environ.setdefault("ALPACA_SECRET_KEY", "test_secret_key")
