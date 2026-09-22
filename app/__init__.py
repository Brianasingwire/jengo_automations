import hashlib
import logging
import os
import secrets
from datetime import date
from functools import lru_cache

from dotenv import load_dotenv
from flask import Flask, current_app, flash, g, render_template, request, url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFError, CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

from .content import load_content
from .icons import icon

csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address)

# Everything (scripts, CSS, fonts) is self-hosted. Inline <script> tags must carry
# nonce="{{ csp_nonce }}".
CSP = (
    "default-src 'self'; "
    "script-src 'self' 'nonce-{nonce}'; "
    "style-src 'self'; "
    "font-src 'self'; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "object-src 'none'"
)


def create_app(overrides=None):
    load_dotenv()
    from .config import Config

    app = Flask(__name__)
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)

    check_production_config(app.config)
    if not app.config["SECRET_KEY"]:
        app.config["SECRET_KEY"] = "dev-only-secret"  # debug/testing only; see check_production_config

    logging.basicConfig(level=logging.INFO)
    # urllib3 logs full request URLs at DEBUG, and the Make webhook URL is a credential.
    # Keep it quiet even if someone lowers the root log level.
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    # Railway and Render terminate TLS at a proxy; trust exactly that many hops so
    # request.remote_addr / is_secure reflect the real client, not the proxy.
    proxies = app.config["TRUSTED_PROXY_COUNT"]
    if proxies:
        # Host is deliberately not trusted from headers: public URLs come from SITE_URL.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=proxies, x_proto=proxies)

    csrf.init_app(app)
    limiter.init_app(app)

    # Load the words once at startup, so a broken content.toml fails the deploy
    # instead of reaching visitors.
    app.extensions["content"] = load_content(app.config["CONTENT_PATH"], app.static_folder)
    app.extensions["content_mtime"] = os.path.getmtime(app.config["CONTENT_PATH"])

    if app.debug:
        @app.before_request
        def reload_changed_content():
            """While previewing locally, pick up content.toml edits on refresh."""
            mtime = os.path.getmtime(app.config["CONTENT_PATH"])
            if mtime != app.extensions["content_mtime"]:
                app.extensions["content"] = load_content(app.config["CONTENT_PATH"], app.static_folder)
                app.extensions["content_mtime"] = mtime

    from .forms import ContactForm, form_snapshot
    from .leads import log_unsent_lead
    from .routes import bp, human_form_age, issue_form_token, may_log_unsent_lead, read_form_token

    app.register_blueprint(bp)
    app.jinja_env.globals["icon"] = icon

    @lru_cache(maxsize=None)
    def _file_hash(path):
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:10]

    def asset_url(filename):
        """url_for('static') with a content-hash query string for long-lived caching."""
        path = os.path.join(app.static_folder, filename)
        version = _file_hash(path) if not app.debug else int(os.path.getmtime(path))
        return url_for("static", filename=filename, v=version)

    def csp_nonce():
        if "csp_nonce" not in g:
            g.csp_nonce = secrets.token_urlsafe(16)
        return g.csp_nonce

    @app.context_processor
    def inject_globals():
        return {
            "site_name": app.config["SITE_NAME"],
            "site_url": app.config["SITE_URL"],
            "contact_email": app.config["CONTACT_EMAIL"],
            "asset_url": asset_url,
            "csp_nonce": csp_nonce(),
            "current_year": date.today().year,
        }

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("Content-Security-Policy", CSP.format(nonce=csp_nonce()))
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resp.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        if request.is_secure:
            hsts = "max-age=31536000"
            if app.config["HSTS_INCLUDE_SUBDOMAINS"]:
                hsts += "; includeSubDomains"
            resp.headers.setdefault("Strict-Transport-Security", hsts)
        return resp

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(CSRFError)
    def csrf_failed(_e):
        # Usually a lost or expired session cookie on a genuine enquiry: keep what they
        # typed and let them resend, rather than showing a bare 400 page.
        if request.endpoint != "main.contact":
            return render_template("errors/400.html"), 400
        # Only log what looks like a person's enquiry: bots posting without the form
        # would otherwise fill the logs with fake leads.
        if human_form_age(request.form) is not None and may_log_unsent_lead(request.remote_addr):
            log_unsent_lead("Contact form CSRF check failed", form_snapshot(request.form))
        form = ContactForm(formdata=request.form)
        # Keep their original signed token (never a pre-aged one, which bots could harvest
        # to skip the minimum fill time); issue a fresh one if theirs isn't valid.
        if read_form_token(request.form.get("started")) is None:
            form.started.data = issue_form_token()
        flash("Your session expired before we received your enquiry. Please check your details and press Send again.", "error")
        return render_template("pages/contact.html", form=form), 400

    @app.errorhandler(429)
    def too_many_requests(_e):
        if (
            request.method == "POST"
            and request.endpoint == "main.contact"
            and human_form_age(request.form) is not None
            and may_log_unsent_lead(request.remote_addr)
        ):
            log_unsent_lead("Contact form rate-limited", form_snapshot(request.form))
        return render_template("errors/429.html"), 429

    @app.errorhandler(500)
    def server_error(_e):
        return render_template("errors/500.html"), 500

    return app


def _is_local(site_url):
    return "localhost" in site_url or "127.0.0.1" in site_url


def check_production_config(config):
    """Refuse to start a public deployment with missing or placeholder settings."""
    if config["DEBUG"] and config["SITE_URL"].startswith("https://"):
        raise RuntimeError("FLASK_DEBUG=1 on a public https SITE_URL: turn debug off in production.")
    if config["DEBUG"] and not config["SECRET_KEY"] and not _is_local(config["SITE_URL"]):
        # The dev fallback key is public (it's in this file), so sessions would be forgeable.
        raise RuntimeError("SECRET_KEY is not set and SITE_URL isn't local: set SECRET_KEY.")
    if config["DEBUG"] or config["TESTING"]:
        return

    problems = []
    if not config["SECRET_KEY"]:
        problems.append("SECRET_KEY is not set")
    if not config["MAKE_WEBHOOK_URL"]:
        problems.append("MAKE_WEBHOOK_URL is not set (leads would never reach Make)")
    if _is_local(config["SITE_URL"]):
        problems.append(f"SITE_URL is a local address ({config['SITE_URL']})")
    if config["CONTACT_EMAIL"].endswith(".example"):
        problems.append(f"CONTACT_EMAIL is the placeholder {config['CONTACT_EMAIL']}")
    if problems:
        raise RuntimeError("Refusing to start in production: " + "; ".join(problems) + ". See .env.example.")


def site_content():
    """The parsed content.toml for the running app."""
    return current_app.extensions["content"]
