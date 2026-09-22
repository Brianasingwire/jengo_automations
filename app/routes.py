import secrets
import time
from collections import deque
from urllib.parse import urlsplit

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from itsdangerous import BadSignature, URLSafeSerializer

from . import csrf, limiter, site_content
from .forms import ContactForm, form_snapshot
from .leads import SERVICE_OPTIONS, build_payload, log_unsent_lead, send_lead

bp = Blueprint("main", __name__)

# Endpoints listed in sitemap.xml, with their relative priority.
SITEMAP_PAGES = [
    ("main.home", "1.0"),
    ("main.services", "0.9"),
    ("main.how_it_works", "0.8"),
    ("main.about", "0.7"),
    ("main.contact", "0.9"),
    ("main.privacy", "0.3"),
]

UTM_KEYS = ("utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content")
NO_ATTRIBUTION_ENDPOINTS = {None, "static", "main.healthz", "main.robots", "main.sitemap"}
# Attribution values come from the visitor, so cap them (they live in the session cookie).
MAX_ATTRIBUTION_LENGTH = 300


@bp.app_context_processor
def inject_content():
    return {
        # All site words, from content.toml: c.home.hero.intro, c.services, ...
        "c": site_content(),
        "service_option_ids": {oid for oid, _ in SERVICE_OPTIONS},
    }


@bp.before_app_request
def capture_attribution():
    """Remember first-touch attribution so it can be sent with the lead."""
    if request.endpoint in NO_ATTRIBUTION_ENDPOINTS or "attribution" in session:
        return
    attribution = {
        "landing_page": request.path,
        "referrer": _referrer_origin_and_path(request.referrer),
        **{k: request.args[k] for k in UTM_KEYS if k in request.args},
    }
    session["attribution"] = {k: v[:MAX_ATTRIBUTION_LENGTH] for k, v in attribution.items()}


def _referrer_origin_and_path(referrer):
    """Keep scheme://host/path only; query strings can carry other sites' tokens or personal data."""
    if not referrer:
        return ""
    parts = urlsplit(referrer)
    if parts.scheme not in ("http", "https"):
        return ""
    return f"{parts.scheme}://{parts.netloc}{parts.path}"


# --- Form token: signed [render time, one-time id] in the hidden `started` field ---
# Proves the form was rendered by us, when, and that this copy hasn't been sent before.

USED_FORMS_KEPT = 20


def _form_signer():
    return URLSafeSerializer(current_app.config["SECRET_KEY"], salt="contact-form-started")


def issue_form_token(started_at=None):
    started_at = started_at if started_at is not None else time.time()
    return _form_signer().dumps([started_at, secrets.token_urlsafe(8)])


def read_form_token(token):
    """(render time, form id) from a signed token, or None if it's missing or tampered with."""
    try:
        started_at, form_id = _form_signer().loads(token or "")
        return float(started_at), str(form_id)
    except (BadSignature, TypeError, ValueError):
        return None


def human_form_age(formdata):
    """Seconds since this form was rendered, if the submission looks like it came from a
    person: empty honeypot, a genuine unused token, and filled in slowly enough. Else None."""
    if formdata.get("website"):
        return None
    token = read_form_token(formdata.get("started"))
    if token is None:
        return None
    started_at, form_id = token
    if form_id in session.get("used_forms", []):
        return None
    elapsed = time.time() - started_at
    if elapsed < current_app.config["MIN_FORM_FILL_SECONDS"]:
        return None
    return elapsed


def mark_form_used(token):
    _, form_id = read_form_token(token)
    session["used_forms"] = (session.get("used_forms", []) + [form_id])[-USED_FORMS_KEPT:]


def may_log_unsent_lead(ip):
    """Cap how many unsent leads one IP can write to the logs per hour, so nobody can flood them."""
    per_ip = current_app.extensions.setdefault("unsent_log_times", {})
    if len(per_ip) > 10_000:  # bound memory; per-worker and reset on deploy anyway
        per_ip.clear()
    now = time.time()
    times = per_ip.setdefault(ip, deque())
    while times and now - times[0] > 3600:
        times.popleft()
    if len(times) >= current_app.config["UNSENT_LEAD_LOGS_PER_HOUR"]:
        return False
    times.append(now)
    return True


@bp.route("/")
def home():
    return render_template("pages/home.html")


@bp.route("/services")
def services():
    return render_template("pages/services.html")


@bp.route("/how-it-works")
def how_it_works():
    return render_template("pages/how_it_works.html")


@bp.route("/about")
def about():
    return render_template("pages/about.html")


@bp.route("/contact", methods=["GET", "POST"])
# CSRF is checked inside the view instead of globally, so it runs *after* the rate
# limits below: rejected POSTs must still count towards CONTACT_POST_LIMIT.
@csrf.exempt
# Only accepted submissions (redirects) use up this allowance; see CONTACT_RATE_LIMIT.
@limiter.limit(
    lambda: current_app.config["CONTACT_RATE_LIMIT"],
    methods=["POST"],
    deduct_when=lambda resp: resp.status_code == 302,
)
# A looser cap on every POST, including rejected ones (bad CSRF token, validation errors).
@limiter.limit(lambda: current_app.config["CONTACT_POST_LIMIT"], methods=["POST"])
def contact():
    if request.method == "POST" and current_app.config["WTF_CSRF_ENABLED"]:
        csrf.protect()  # raises CSRFError -> app.csrf_failed, like the global check
    form = ContactForm()
    # Allow deep links like /contact?service=ai_agents to preselect a service.
    if request.method == "GET" and request.args.get("service"):
        form.service_type.data = request.args["service"]

    if form.validate_on_submit():
        elapsed = human_form_age(request.form)
        if elapsed is None:
            current_app.logger.info("Dropped likely-spam submission from %s", request.remote_addr)
            return redirect(url_for("main.thanks"))

        if elapsed > current_app.config["FORM_MAX_AGE_SECONDS"]:
            # A genuine but very old form: ask them to confirm. The new token is backdated so the
            # resend isn't mistaken for a bot; only a real signed form >24h old can get here.
            if may_log_unsent_lead(request.remote_addr):
                log_unsent_lead("Contact form open too long; asked to resend", form_snapshot(request.form))
            form.started.data = issue_form_token(time.time() - current_app.config["MIN_FORM_FILL_SECONDS"])
            flash("This page was open for a long time, so please press Send again to confirm.", "error")
            return render_template("pages/contact.html", form=form)

        lead = {f: getattr(form, f).data for f in ("name", "email", "service_type", "budget", "timeline", "message")}
        lead["name"] = lead["name"].strip()
        lead["email"] = lead["email"].strip().lower()
        meta = {**session.get("attribution", {}), "source": "website", "page": request.path}

        payload = build_payload(lead, meta)
        ok = send_lead(
            payload,
            current_app.config["MAKE_WEBHOOK_URL"],
            current_app.config["WEBHOOK_TIMEOUT_SECONDS"],
        )
        if ok:
            mark_form_used(form.started.data)
            session["lead_first_name"] = lead["name"].split()[0] if lead["name"] else ""
            return redirect(url_for("main.thanks"))

        flash(
            "Sorry, something went wrong on our side and your message wasn't sent. "
            f"Please try again, or email us at {current_app.config['CONTACT_EMAIL']}.",
            "error",
        )

    # Keep a valid submitted token across re-renders (validation errors, webhook failure)
    # so the retry isn't mistaken for a bot; otherwise start the timer now.
    if read_form_token(form.started.data) is None:
        form.started.data = issue_form_token()
    return render_template("pages/contact.html", form=form)


@bp.route("/case-studies/<slug>")
def case_study(slug):
    study = next((cs for cs in site_content()["case_studies"] if cs["slug"] == slug), None)
    if study is None:
        abort(404)
    return render_template("pages/case_study.html", study=study)


@bp.route("/thanks")
def thanks():
    return render_template("pages/thanks.html", first_name=session.pop("lead_first_name", ""))


@bp.route("/privacy")
def privacy():
    return render_template("pages/privacy.html")


@bp.route("/robots.txt")
def robots():
    body = f"User-agent: *\nDisallow: /thanks\n\nSitemap: {current_app.config['SITE_URL']}/sitemap.xml\n"
    resp = make_response(body)
    resp.mimetype = "text/plain"
    return resp


@bp.route("/sitemap.xml")
def sitemap():
    pages = [(url_for(endpoint), priority) for endpoint, priority in SITEMAP_PAGES]
    pages += [(url_for("main.case_study", slug=cs["slug"]), "0.6") for cs in site_content()["case_studies"]]
    resp = make_response(render_template("sitemap.xml", pages=pages))
    resp.mimetype = "application/xml"
    return resp


@bp.route("/healthz")
def healthz():
    return {"status": "ok"}
