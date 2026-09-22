import re
from unittest.mock import patch

import pytest
import requests

from app.leads import BUDGET_OPTIONS, SERVICE_OPTIONS, TIMELINE_OPTIONS, build_payload
from tests.util import form_data, started_token

VALID = {
    "name": "  Jane Smith ",
    "email": "Jane@Example.com",
    "service_type": "lead_crm",
    "budget": "3k_7k",
    "timeline": "1_month",
    "message": "We use HubSpot.",
}


@pytest.fixture
def mock_post():
    with patch("app.leads.requests.post") as post:
        post.return_value.raise_for_status.return_value = None
        yield post


def test_valid_submission_posts_payload_and_redirects(client, mock_post):
    resp = client.post("/contact", data=form_data(client, VALID, path="/contact?utm_source=google&utm_campaign=brand"))

    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/thanks")
    assert mock_post.call_args.args[0] == "https://hook.test/abc"

    payload = mock_post.call_args.kwargs["json"]
    assert payload["name"] == "Jane Smith"
    assert payload["email"] == "jane@example.com"
    assert payload["service_type"] == "Lead Generation & CRM Automation"
    assert payload["service_type_id"] == "lead_crm"
    assert payload["budget"] == "$3,000 – $7,500"
    assert payload["budget_id"] == "3k_7k"
    assert payload["timeline"] == "Within 1 month"
    assert payload["timeline_id"] == "1_month"
    assert payload["message"] == "We use HubSpot."
    assert payload["meta"]["utm_source"] == "google"
    assert payload["meta"]["landing_page"] == "/contact"

    assert "Jane" in client.get("/thanks").get_data(as_text=True)


@pytest.mark.parametrize("field,value", [
    ("email", "not-an-email"),
    ("service_type", ""),
    ("budget", "a-million-dollars"),
    ("timeline", ""),
    ("name", ""),
])
def test_invalid_submission_is_not_sent(client, mock_post, field, value):
    resp = client.post("/contact", data=form_data(client, {**VALID, field: value}))
    assert resp.status_code == 200
    assert 'aria-invalid="true"' in resp.get_data(as_text=True)
    mock_post.assert_not_called()


def test_honeypot_is_silently_dropped(client, mock_post):
    resp = client.post("/contact", data=form_data(client, {**VALID, "website": "http://spam.example"}))
    assert resp.status_code == 302
    mock_post.assert_not_called()


def test_too_fast_submission_is_dropped(app, client, mock_post):
    app.config["MIN_FORM_FILL_SECONDS"] = 60
    resp = client.post("/contact", data=form_data(client, VALID))
    assert resp.status_code == 302
    mock_post.assert_not_called()


@pytest.mark.parametrize("started", [None, "", "not-a-signed-value", "1000.0"])
def test_missing_or_forged_timer_is_dropped(app, client, mock_post, started):
    """Regression: a missing timestamp used to count as 'filled in slowly'."""
    app.config["MIN_FORM_FILL_SECONDS"] = 3
    data = dict(VALID) if started is None else {**VALID, "started": started}
    resp = client.post("/contact", data=data)
    assert resp.status_code == 302
    mock_post.assert_not_called()


def test_dropping_spam_does_not_unlock_the_next_post(app, client, mock_post):
    """Regression: dropping a too-fast post used to clear the timer, so the retry passed."""
    app.config["MIN_FORM_FILL_SECONDS"] = 60
    data = form_data(client, VALID)
    client.post("/contact", data=data)
    client.post("/contact", data=data)
    client.post("/contact", data=VALID)
    mock_post.assert_not_called()


def test_slow_enough_submission_is_sent(app, client, mock_post):
    app.config["MIN_FORM_FILL_SECONDS"] = 3
    with patch("app.routes.time.time", return_value=1_000_000.0):
        token = started_token(client)
    with patch("app.routes.time.time", return_value=1_000_005.0):
        resp = client.post("/contact", data={**VALID, "started": token})
    assert resp.status_code == 302
    mock_post.assert_called_once()


def test_form_left_open_too_long_asks_to_resend(app, client, mock_post):
    app.config["MIN_FORM_FILL_SECONDS"] = 3
    with patch("app.routes.time.time", return_value=1_000_000.0):
        token = started_token(client)
    with patch("app.routes.time.time", return_value=1_000_000.0 + 2 * 86400):
        resp = client.post("/contact", data={**VALID, "started": token})
        html = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert "press Send again" in html
        assert 'value="Jane@Example.com"' in html
        mock_post.assert_not_called()

        # The re-shown form carries a fresh timestamp that passes straight away.
        fresh = re.search(r'name="started" type="hidden" value="([^"]+)"', html).group(1)
        assert client.post("/contact", data={**VALID, "started": fresh}).status_code == 302
    mock_post.assert_called_once()


def test_validation_error_keeps_the_original_timer(app, client, mock_post):
    app.config["MIN_FORM_FILL_SECONDS"] = 3
    with patch("app.routes.time.time", return_value=1_000_000.0):
        token = started_token(client)
    with patch("app.routes.time.time", return_value=1_000_010.0):
        html = client.post("/contact", data={**VALID, "email": "nope", "started": token}).get_data(as_text=True)
        assert f'value="{token}"' in html
        # Fixing the typo and resending immediately isn't mistaken for a bot.
        assert client.post("/contact", data={**VALID, "started": token}).status_code == 302
    mock_post.assert_called_once()


def test_webhook_failure_shows_error_and_keeps_input(client, mock_post, caplog):
    mock_post.side_effect = requests.ConnectionError("boom")
    resp = client.post("/contact", data=form_data(client, VALID))
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "wasn&#39;t sent" in html
    assert 'value="Jane@Example.com"' in html
    assert "LEAD PAYLOAD" in caplog.text


def test_webhook_url_never_reaches_the_logs(client, mock_post, caplog):
    """Regression: requests puts the full (secret) URL in HTTPError messages."""
    secret_url = "https://hook.eu1.make.com/SECRETPATH123"
    error = requests.HTTPError(f"410 Client Error: Gone for url: {secret_url}")
    error.response = type("Resp", (), {"status_code": 410})()
    mock_post.return_value.raise_for_status.side_effect = error
    client.post("/contact", data=form_data(client, VALID))
    assert "SECRETPATH123" not in caplog.text
    assert "HTTPError, HTTP 410" in caplog.text
    assert "LEAD PAYLOAD" in caplog.text


def test_csrf_is_enforced_by_default(mock_post):
    from app import create_app

    app = create_app({"TESTING": True, "SESSION_COOKIE_SECURE": False, "MAKE_WEBHOOK_URL": "https://hook.test/abc"})
    resp = app.test_client().post("/contact", data=VALID)
    assert resp.status_code == 400
    mock_post.assert_not_called()


def _csrf_app(**overrides):
    from app import create_app

    return create_app({
        "TESTING": True,
        "SESSION_COOKIE_SECURE": False,
        "MAKE_WEBHOOK_URL": "https://hook.test/abc",
        "MIN_FORM_FILL_SECONDS": 3,
        "RATELIMIT_ENABLED": False,
        **overrides,
    })


def _hidden_fields(html):
    return dict(re.findall(r'name="(csrf_token|started)" type="hidden" value="([^"]+)"', html))


def test_csrf_failure_keeps_a_real_enquiry_and_logs_it(caplog, mock_post):
    """Regression: a lost/expired session used to show a bare 400 and lose the lead."""
    app = _csrf_app()
    with patch("app.routes.time.time", return_value=1_000_000.0):
        started = _hidden_fields(app.test_client().get("/contact").get_data(as_text=True))["started"]

    # Same visitor, but their session cookie is gone (new client), so CSRF fails.
    client = app.test_client()
    with patch("app.routes.time.time", return_value=1_000_060.0):
        resp = client.post("/contact", data={**VALID, "started": started, "csrf_token": "stale"})
        html = resp.get_data(as_text=True)
        assert resp.status_code == 400
        assert "press Send again" in html
        assert 'value="Jane@Example.com"' in html
        assert "Contact form CSRF check failed. LEAD PAYLOAD:" in caplog.text
        assert "HubSpot" in caplog.text

        # Their original token is kept, so resending straight away goes through.
        fields = _hidden_fields(html)
        assert fields["started"] == started
        assert client.post("/contact", data={**VALID, **fields}).status_code == 302
    mock_post.assert_called_once()


def test_bot_posts_without_a_form_are_not_logged(caplog, mock_post):
    """Regression: token-less bot POSTs were each logged as a 'lead', flooding the logs."""
    client = _csrf_app().test_client()
    for _ in range(5):
        assert client.post("/contact", data={**VALID, "csrf_token": "x"}).status_code == 400
    assert "LEAD PAYLOAD" not in caplog.text
    mock_post.assert_not_called()


def test_csrf_page_cannot_be_harvested_to_skip_the_fill_timer(mock_post):
    """Regression: the CSRF page used to hand out a pre-aged timestamp, so a bot could fail
    once, copy the tokens and resubmit instantly."""
    client = _csrf_app(MIN_FORM_FILL_SECONDS=30).test_client()
    fields = _hidden_fields(client.post("/contact", data={**VALID, "csrf_token": "x"}).get_data(as_text=True))
    assert client.post("/contact", data={**VALID, **fields}).status_code == 302  # silently dropped
    mock_post.assert_not_called()


def test_unsent_lead_logging_is_capped_per_ip(caplog, mock_post):
    app = _csrf_app(UNSENT_LEAD_LOGS_PER_HOUR=2)
    with patch("app.routes.time.time", return_value=1_000_000.0):
        started = _hidden_fields(app.test_client().get("/contact").get_data(as_text=True))["started"]
    with patch("app.routes.time.time", return_value=1_000_060.0):
        for _ in range(5):
            app.test_client().post("/contact", data={**VALID, "started": started, "csrf_token": "stale"})
    assert caplog.text.count("LEAD PAYLOAD") == 2


def test_a_form_can_only_be_sent_once(client, mock_post):
    """A captured form token can't be replayed to send many leads."""
    data = form_data(client, VALID)
    assert client.post("/contact", data=data).status_code == 302
    assert client.post("/contact", data=data).status_code == 302  # replay silently dropped
    mock_post.assert_called_once()


def test_csrf_token_does_not_expire_after_an_hour(app):
    assert app.config["WTF_CSRF_TIME_LIMIT"] is None


def test_option_ids_are_pinned():
    """The ids are the contract with the Make scoring scenario. Adding one is fine
    (update this test and the Make switch together); renaming or removing one breaks scoring."""
    assert [i for i, _ in SERVICE_OPTIONS] == [
        "workflow_automation", "ai_agents", "lead_crm", "document_ai", "reporting", "care_plan", "not_sure",
    ]
    assert [i for i, _ in BUDGET_OPTIONS] == ["under_1k", "1k_3k", "3k_7k", "7k_15k", "15k_plus"]
    assert [i for i, _ in TIMELINE_OPTIONS] == ["asap", "1_month", "1_3_months", "exploring"]


def test_every_option_label_is_unique():
    from app.leads import CHOICE_FIELDS

    for options in CHOICE_FIELDS.values():
        labels = [label for _, label in options]
        assert len(labels) == len(set(labels))


def test_empty_message_is_empty_string():
    payload = build_payload({**VALID, "message": None}, {})
    assert payload["message"] == ""
