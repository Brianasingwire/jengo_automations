import pytest

from app import create_app


@pytest.fixture
def app():
    return create_app({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SESSION_COOKIE_SECURE": False,
        "MIN_FORM_FILL_SECONDS": 0,
        "MAKE_WEBHOOK_URL": "https://hook.test/abc",
        "SITE_URL": "https://jengo.test",
    })


@pytest.fixture
def client(app):
    return app.test_client()
