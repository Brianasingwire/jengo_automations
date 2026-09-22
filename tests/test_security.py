import re
from unittest.mock import patch

import pytest

from app import check_production_config, create_app
from tests.util import form_data

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


def test_csp_has_no_unsafe_directives_or_third_party_origins(client):
    csp = client.get("/").headers["Content-Security-Policy"]
    assert "unsafe-eval" not in csp and "unsafe-inline" not in csp
    assert "https://" not in csp  # scripts, styles and fonts are all self-hosted


def test_pages_load_no_third_party_assets(client):
    html = client.get("/").get_data(as_text=True)
    external = re.findall(r'<script[^>]*src="https?://[^"]*"|<link[^>]*rel="(?:stylesheet|preload|preconnect)"[^>]*href="https?://[^"]*"', html)
    assert not external


def test_hsts_include_subdomains_is_opt_in():
    app = make_app(HSTS_INCLUDE_SUBDOMAINS=True)
    resp = app.test_client().get("/", headers={"X-Forwarded-Proto": "https"})
    assert resp.headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"


def test_forwarded_host_is_not_trusted():
    app = make_app()
    seen = {}

    @app.get("/_host")
    def _host():
        from flask import request
        seen["host"] = request.host
        return ""

    app.test_client().get("/_host", headers={"X-Forwarded-Host": "evil.example"})
    assert seen["host"] != "evil.example"


PROD = {
    "DEBUG": False,
    "TESTING": False,
    "SECRET_KEY": "x" * 32,
    "MAKE_WEBHOOK_URL": "https://hook.test/abc",
    "SITE_URL": "https://jengo.test",
    "CONTACT_EMAIL": "hello@jengo.test",
}


def test_valid_production_config_starts():
    check_production_config(PROD)


@pytest.mark.parametrize("key,value,message", [
    ("SECRET_KEY", "", "SECRET_KEY"),
    ("MAKE_WEBHOOK_URL", "", "MAKE_WEBHOOK_URL"),
    ("SITE_URL", "http://localhost:5000", "SITE_URL"),
    ("CONTACT_EMAIL", "hello@jengo.example", "CONTACT_EMAIL"),
])
def test_production_refuses_missing_or_placeholder_settings(key, value, message):
    with pytest.raises(RuntimeError, match=message):
        check_production_config({**PROD, key: value})


def test_debug_is_refused_on_a_public_site():
    with pytest.raises(RuntimeError, match="FLASK_DEBUG"):
        check_production_config({**PROD, "DEBUG": True, "SECRET_KEY": ""})


def test_dev_secret_is_refused_anywhere_but_localhost():
    """Regression: debug + http SITE_URL used to start with the public dev key."""
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        check_production_config({**PROD, "DEBUG": True, "SECRET_KEY": "", "SITE_URL": "http://jengo.test"})
    check_production_config({**PROD, "DEBUG": True, "SECRET_KEY": "", "SITE_URL": "http://localhost:5000"})


def test_rejected_posts_count_towards_the_loose_limit():
    """Bots posting without a valid form are rate-limited too, not just accepted leads."""
    app = create_app({
        "TESTING": True, "SESSION_COOKIE_SECURE": False, "MAKE_WEBHOOK_URL": "https://hook.test/abc",
        "RATELIMIT_ENABLED": True, "RATELIMIT_STORAGE_URI": "memory://", "CONTACT_POST_LIMIT": "3 per hour",
    })
    client = app.test_client()
    codes = [client.post("/contact", data={**VALID, "csrf_token": "x"}).status_code for _ in range(4)]
    assert codes == [400, 400, 400, 429]


def test_urllib3_cannot_log_the_webhook_url(client):
    import logging

    assert logging.getLogger("urllib3").getEffectiveLevel() >= logging.WARNING


def test_attribution_is_truncated_and_referrer_stripped(client):
    with patch("app.leads.requests.post") as post:
        post.return_value.raise_for_status.return_value = None
        data = form_data(
            client, VALID,
            path="/contact?utm_source=" + "a" * 5000,
            headers={"Referer": "https://google.com/search?q=secret+stuff"},
        )
        client.post("/contact", data=data)
    meta = post.call_args.kwargs["json"]["meta"]
    assert len(meta["utm_source"]) == 300
    assert meta["referrer"] == "https://google.com/search"


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
        ip1 = {"X-Forwarded-For": "198.51.100.1"}
        codes = [client.post("/contact", data=form_data(client, VALID, headers=ip1), headers=ip1).status_code for _ in range(3)]
        assert codes == [302, 302, 429]
        assert post.call_count == 2

        # A different client IP has its own budget, and GETs are never limited.
        ip2 = {"X-Forwarded-For": "198.51.100.2"}
        assert client.post("/contact", data=form_data(client, VALID, headers=ip2), headers=ip2).status_code == 302
        assert client.get("/contact", headers={"X-Forwarded-For": "198.51.100.1"}).status_code == 200


def test_rate_limit_page_offers_email_fallback_and_logs_the_lead(caplog):
    app = make_app(RATELIMIT_ENABLED=True, CONTACT_RATE_LIMIT="1 per hour", RATELIMIT_STORAGE_URI="memory://")
    client = app.test_client()
    with patch("app.leads.requests.post"):
        client.post("/contact", data=form_data(client, VALID))
        resp = client.post("/contact", data=form_data(client, VALID))
    assert resp.status_code == 429
    assert "mailto:" in resp.get_data(as_text=True)
    assert "Contact form rate-limited. LEAD PAYLOAD:" in caplog.text


def test_validation_errors_do_not_use_up_the_rate_limit():
    """Only accepted submissions count, so typos (or a shared mobile-carrier IP) don't lock people out."""
    app = make_app(RATELIMIT_ENABLED=True, CONTACT_RATE_LIMIT="1 per hour", RATELIMIT_STORAGE_URI="memory://")
    client = app.test_client()
    with patch("app.leads.requests.post") as post:
        for _ in range(3):
            assert client.post("/contact", data=form_data(client, {**VALID, "email": "typo"})).status_code == 200
        assert client.post("/contact", data=form_data(client, VALID)).status_code == 302
        assert post.call_count == 1
