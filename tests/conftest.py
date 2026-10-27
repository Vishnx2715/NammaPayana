"""
Shared pytest fixtures for Namma Payana tests.
"""
import pytest
from app import app as flask_app


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    flask_app.config["WTF_CSRF_ENABLED"] = False
    flask_app.config["RATELIMIT_ENABLED"] = False
    with flask_app.test_client() as c:
        yield c
    flask_app.config["WTF_CSRF_ENABLED"] = True
    flask_app.config["RATELIMIT_ENABLED"] = True
