import hashlib
import logging
import os
import secrets
from datetime import date
from functools import lru_cache

from dotenv import load_dotenv
from flask import Flask, g, render_template, request, url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

from .icons import icon

csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address)

# Alpine's standard build evaluates directive expressions with Function(), hence 'unsafe-eval'.
# Inline <script> tags must carry nonce="{{ csp_nonce }}".
CSP = (
    "default-src 'self'; "
    "script-src 'self' 'nonce-{nonce}' 'unsafe-eval' https://cdn.jsdelivr.net; "
    "style-src 'self' https://fonts.googleapis.com; "
    "font-src https://fonts.gstatic.com; "
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

    if not app.config["SECRET_KEY"]:
        if app.debug or app.testing:
            app.config["SECRET_KEY"] = "dev-only-secret"
        else:
            raise RuntimeError("SECRET_KEY must be set in production.")

    logging.basicConfig(level=logging.INFO)
    if not app.config["MAKE_WEBHOOK_URL"] and not (app.debug or app.testing):
        app.logger.error("MAKE_WEBHOOK_URL is not set: leads will only be written to the logs.")

    # Railway and Render terminate TLS at a proxy; trust exactly that many hops so
    # request.remote_addr / is_secure reflect the real client, not the proxy.
    proxies = app.config["TRUSTED_PROXY_COUNT"]
    if proxies:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=proxies, x_proto=proxies, x_host=proxies)

    csrf.init_app(app)
    limiter.init_app(app)

    from .routes import bp

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
            resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
        return resp

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(429)
    def too_many_requests(_e):
        return render_template("errors/429.html"), 429

    @app.errorhandler(500)
    def server_error(_e):
        return render_template("errors/500.html"), 500

    return app
