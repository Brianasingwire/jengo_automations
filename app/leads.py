"""Lead capture: form choices and the payload sent to the Make.com lead-scoring webhook.

Each choice is sent twice: as a human-readable label (e.g. `budget`) and as a stable
id (e.g. `budget_id`). Score on the `*_id` fields in Make's switch() so copy edits
to the labels can't silently break scoring.
"""

import json
import logging
import uuid
from datetime import datetime, timezone

import requests

log = logging.getLogger(__name__)

# (stable id, label). The ids are the contract with the Make scenario: never rename or
# remove one (tests/test_contact.py pins them). Ids are opaque keys, so one that no
# longer matches its label (e.g. "3k_7k" for "$3,000 – $7,500") is fine; leave it.
SERVICE_OPTIONS = [
    ("workflow_automation", "Workflow Automation"),
    ("ai_agents", "AI Agents & Chatbots"),
    ("lead_crm", "Lead Generation & CRM Automation"),
    ("document_ai", "AI Document Processing"),
    ("reporting", "Reporting & Data Pipelines"),
    ("care_plan", "Care Plans & Ongoing Support"),
    ("not_sure", "Not sure yet"),
]

BUDGET_OPTIONS = [
    ("under_1k", "Under $1,000"),
    ("1k_3k", "$1,000 – $3,000"),
    ("3k_7k", "$3,000 – $7,500"),
    ("7k_15k", "$7,500 – $15,000"),
    ("15k_plus", "$15,000+"),
]

TIMELINE_OPTIONS = [
    ("asap", "ASAP (within 2 weeks)"),
    ("1_month", "Within 1 month"),
    ("1_3_months", "1–3 months"),
    ("exploring", "Just exploring"),
]

CHOICE_FIELDS = {
    "service_type": SERVICE_OPTIONS,
    "budget": BUDGET_OPTIONS,
    "timeline": TIMELINE_OPTIONS,
}


def build_payload(lead, meta):
    """Build the webhook body. `lead` maps field name -> submitted value (choice fields hold option ids)."""
    payload = {
        "submission_id": uuid.uuid4().hex,
        "submitted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "name": lead["name"],
        "email": lead["email"],
    }
    for field, options in CHOICE_FIELDS.items():
        payload[field] = dict(options)[lead[field]]
        payload[f"{field}_id"] = lead[field]
    payload["message"] = lead.get("message") or ""
    payload["meta"] = meta
    return payload


def send_lead(payload, webhook_url, timeout):
    """POST the lead to Make. Returns True on success.

    On failure the full payload is logged so the lead can be recovered from the host's logs.
    """
    if not webhook_url:
        log.warning("MAKE_WEBHOOK_URL not set; lead not forwarded: %s", json.dumps(payload))
        return True

    try:
        resp = requests.post(webhook_url, json=payload, timeout=timeout)
        resp.raise_for_status()
        return True
    except requests.RequestException as exc:
        # Never log str(exc): requests puts the full webhook URL (a credential) in it.
        status = getattr(exc.response, "status_code", None)
        reason = f"{type(exc).__name__}, HTTP {status}" if status else type(exc).__name__
        log_unsent_lead(f"Lead webhook failed ({reason})", payload)
        return False


def log_unsent_lead(reason, data):
    """Log a lead that didn't reach Make, so it can be recovered from the host's logs.

    json.dumps escapes newlines, so user input can't forge extra log lines.
    """
    log.error("%s. LEAD PAYLOAD: %s", reason, json.dumps(data))
