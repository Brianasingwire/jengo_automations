import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or ""
    DEBUG = os.environ.get("FLASK_DEBUG") == "1"
    TESTING = False

    SITE_NAME = "Jengo"
    SITE_URL = os.environ.get("SITE_URL", "http://localhost:5000").rstrip("/")
    CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "hello@jengo.example")

    MAKE_WEBHOOK_URL = os.environ.get("MAKE_WEBHOOK_URL", "")
    WEBHOOK_TIMEOUT_SECONDS = 10

    # Submissions faster than this after the form was rendered are treated as bots.
    MIN_FORM_FILL_SECONDS = 3

    # Static assets are cache-busted by content hash (see asset_url), so cache aggressively.
    SEND_FILE_MAX_AGE_DEFAULT = 60 * 60 * 24 * 365

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = not DEBUG
