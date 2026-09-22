import re
from unittest.mock import patch

from app import create_app

VALID = {"name": "Jane", "email": "jane@example.com", "service_type": "ai_agents", "budget": "1k_3k", "timeline": "asap"}


def make_app(**overrides):
    return create_app({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SESSION_COOKIE_SECURE": False,
        "MIN_FORM_FILL_SECONDS": 0,
        "MAKE_WEBHOOK_URL": "https://hook.test/abc",
        "RATELIMIT_ENABLED": False,
        **overrides,
    })


def test_security_headers_and_csp_nonce_matches_inline_scripts(client):
    resp = client.get("/")
    csp = resp.headers["Content-Security-Policy"]
    nonce = re.search(r"'nonce-([^']+)'", csp).group(1)
    html = resp.get_data(as_text=True)

    inline_scripts = re.findall(r"<script(?![^>]*\bsrc=)(?![^>]*application/ld\+json)([^>]*)>", html)
    assert inline_scripts, "expected inline scripts in base.html"
    assert all(f'nonce="{nonce}"' in attrs for attrs in inline_scripts)

    assert "frame-ancestors 'none'" in csp and "object-src 'none'" in csp
    assert resp.headers["Permissions-Policy"].startswith("camera=()")
    assert resp.headers["X-Frame-Options"] == "DENY"


def test_nonce_changes_per_request(client):
    a = client.get("/").headers["Content-Security-Policy"]
    b = client.get("/").headers["Content-Security-Policy"]
    assert a != b


def test_hsts_only_over_https(client):
    assert "Strict-Transport-Security" not in client.get("/").headers
    resp = client.get("/", headers={"X-Forwarded-Proto": "https"})
    assert resp.headers["Strict-Transport-Security"] == "max-age=31536000"


def test_external_scripts_have_sri(client):
    html = client.get("/").get_data(as_text=True)
    for tag in re.findall(r"<script[^>]*\bsrc=\"https://[^>]*>", html):
        assert 'integrity="sha384-' in tag and 'crossorigin="anonymous"' in tag, tag


def test_proxy_fix_uses_forwarded_client_ip():
    app = make_app()
    seen = {}

    @app.get("/_ip")
    def _ip():
        from flask import request
        seen["ip"] = request.remote_addr
        return ""

    app.test_client().get("/_ip", headers={"X-Forwarded-For": "203.0.113.7"})
    assert seen["ip"] == "203.0.113.7"


def test_proxy_fix_trusts_only_configured_hops():
    app = make_app()
    seen = {}

    @app.get("/_ip")
    def _ip():
        from flask import request
        seen["ip"] = request.remote_addr
        return ""

    # A client-forged left-most entry must be ignored; only the proxy-appended one counts.
    app.test_client().get("/_ip", headers={"X-Forwarded-For": "1.2.3.4, 203.0.113.7"})
    assert seen["ip"] == "203.0.113.7"


def test_contact_posts_are_rate_limited_per_ip():
    app = make_app(RATELIMIT_ENABLED=True, CONTACT_RATE_LIMIT="2 per hour", RATELIMIT_STORAGE_URI="memory://")
    client = app.test_client()
    with patch("app.leads.requests.post") as post:
        post.return_value.raise_for_status.return_value = None
        codes = [client.post("/contact", data=VALID, headers={"X-Forwarded-For": "198.51.100.1"}).status_code for _ in range(3)]
        assert codes == [302, 302, 429]
        assert post.call_count == 2

        # A different client IP has its own budget, and GETs are never limited.
        assert client.post("/contact", data=VALID, headers={"X-Forwarded-For": "198.51.100.2"}).status_code == 302
        assert client.get("/contact", headers={"X-Forwarded-For": "198.51.100.1"}).status_code == 200


def test_rate_limit_page_offers_email_fallback():
    app = make_app(RATELIMIT_ENABLED=True, CONTACT_RATE_LIMIT="1 per hour", RATELIMIT_STORAGE_URI="memory://")
    client = app.test_client()
    with patch("app.leads.requests.post"):
        client.post("/contact", data=VALID)
        resp = client.post("/contact", data=VALID)
    assert resp.status_code == 429
    assert "mailto:" in resp.get_data(as_text=True)
