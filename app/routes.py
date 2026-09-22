import time

from flask import (
    Blueprint,
    current_app,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from . import content, limiter
from .forms import ContactForm
from .leads import SERVICE_OPTIONS, build_payload, send_lead

bp = Blueprint("main", __name__)

# Endpoints listed in sitemap.xml, with their relative priority.
SITEMAP_PAGES = [
    ("main.home", "1.0"),
    ("main.services", "0.9"),
    ("main.how_it_works", "0.8"),
    ("main.about", "0.7"),
    ("main.contact", "0.9"),
]

UTM_KEYS = ("utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content")
NO_ATTRIBUTION_ENDPOINTS = {None, "static", "main.healthz", "main.robots", "main.sitemap"}


@bp.app_context_processor
def inject_content():
    return {
        "services": content.SERVICES,
        "process": content.PROCESS,
        "faqs": content.FAQS,
        "tools": content.TOOLS,
        "service_option_ids": {oid for oid, _ in SERVICE_OPTIONS},
    }


@bp.before_app_request
def capture_attribution():
    """Remember first-touch attribution so it can be sent with the lead."""
    if request.endpoint in NO_ATTRIBUTION_ENDPOINTS or "attribution" in session:
        return
    session["attribution"] = {
        "landing_page": request.path,
        "referrer": request.referrer or "",
        **{k: request.args[k] for k in UTM_KEYS if k in request.args},
    }


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
@limiter.limit(lambda: current_app.config["CONTACT_RATE_LIMIT"], methods=["POST"])
def contact():
    form = ContactForm()
    # Allow deep links like /contact?service=ai_agents to preselect a service.
    if request.method == "GET" and request.args.get("service"):
        form.service_type.data = request.args["service"]

    if request.method == "GET":
        session["form_rendered_at"] = time.time()

    if form.validate_on_submit():
        rendered_at = session.pop("form_rendered_at", 0)
        too_fast = time.time() - rendered_at < current_app.config["MIN_FORM_FILL_SECONDS"]
        if form.website.data or too_fast:
            current_app.logger.info("Dropped likely-spam submission from %s", request.remote_addr)
            return redirect(url_for("main.thanks"))

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
            session["lead_first_name"] = lead["name"].split()[0] if lead["name"] else ""
            return redirect(url_for("main.thanks"))

        session["form_rendered_at"] = 0  # the user already spent time on the form
        flash(
            "Sorry, something went wrong on our side and your message wasn't sent. "
            f"Please try again, or email us at {current_app.config['CONTACT_EMAIL']}.",
            "error",
        )

    return render_template("pages/contact.html", form=form)


@bp.route("/thanks")
def thanks():
    return render_template("pages/thanks.html", first_name=session.pop("lead_first_name", ""))


@bp.route("/robots.txt")
def robots():
    body = f"User-agent: *\nDisallow: /thanks\n\nSitemap: {current_app.config['SITE_URL']}/sitemap.xml\n"
    resp = make_response(body)
    resp.mimetype = "text/plain"
    return resp


@bp.route("/sitemap.xml")
def sitemap():
    pages = [(url_for(endpoint), priority) for endpoint, priority in SITEMAP_PAGES]
    resp = make_response(render_template("sitemap.xml", pages=pages))
    resp.mimetype = "application/xml"
    return resp


@bp.route("/healthz")
def healthz():
    return {"status": "ok"}
