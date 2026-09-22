from unittest.mock import patch

import pytest
import requests

from app.leads import build_payload

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
    client.get("/contact?utm_source=google&utm_campaign=brand")
    resp = client.post("/contact", data=VALID)

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
    resp = client.post("/contact", data={**VALID, field: value})
    assert resp.status_code == 200
    assert 'aria-invalid="true"' in resp.get_data(as_text=True)
    mock_post.assert_not_called()


def test_honeypot_is_silently_dropped(client, mock_post):
    resp = client.post("/contact", data={**VALID, "website": "http://spam.example"})
    assert resp.status_code == 302
    mock_post.assert_not_called()


def test_too_fast_submission_is_dropped(app, client, mock_post):
    app.config["MIN_FORM_FILL_SECONDS"] = 60
    client.get("/contact")
    client.post("/contact", data=VALID)
    mock_post.assert_not_called()


def test_webhook_failure_shows_error_and_keeps_input(client, mock_post, caplog):
    mock_post.side_effect = requests.ConnectionError("boom")
    resp = client.post("/contact", data=VALID)
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "wasn&#39;t sent" in html
    assert 'value="Jane@Example.com"' in html
    assert "LEAD PAYLOAD" in caplog.text


def test_csrf_is_enforced_by_default():
    from app import create_app

    app = create_app({"TESTING": True, "SESSION_COOKIE_SECURE": False})
    resp = app.test_client().post("/contact", data=VALID)
    assert resp.status_code == 400


def test_every_option_label_is_unique():
    from app.leads import CHOICE_FIELDS

    for options in CHOICE_FIELDS.values():
        labels = [label for _, label in options]
        assert len(labels) == len(set(labels))


def test_empty_message_is_empty_string():
    payload = build_payload({**VALID, "message": None}, {})
    assert payload["message"] == ""
