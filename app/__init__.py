import hashlib
import logging
import os
from datetime import date
from functools import lru_cache

from dotenv import load_dotenv
from flask import Flask, render_template, url_for
from flask_wtf.csrf import CSRFProtect

from .icons import icon

csrf = CSRFProtect()


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

    csrf.init_app(app)

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

    @app.context_processor
    def inject_globals():
        return {
            "site_name": app.config["SITE_NAME"],
            "site_url": app.config["SITE_URL"],
            "contact_email": app.config["CONTACT_EMAIL"],
            "asset_url": asset_url,
            "current_year": date.today().year,
        }

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return resp

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(_e):
        return render_template("errors/500.html"), 500

    return app
