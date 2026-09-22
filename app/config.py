import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or ""
    DEBUG = os.environ.get("FLASK_DEBUG") == "1"
    TESTING = False

    SITE_NAME = "Jengo"
    # The defaults are dev placeholders; create_app refuses to start in production with them.
    SITE_URL = os.environ.get("SITE_URL", "http://localhost:5000").rstrip("/")
    CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "hello@jengo.example")

    # All the site's words (see the notes at the top of the file).
    CONTENT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "content.toml")

    MAKE_WEBHOOK_URL = os.environ.get("MAKE_WEBHOOK_URL", "")
    WEBHOOK_TIMEOUT_SECONDS = 10

    # Submissions faster than this after the form was rendered are treated as bots. The
    # render time travels in a signed hidden field, so it can't be skipped or forged.
    MIN_FORM_FILL_SECONDS = 3
    # A form older than this must be re-sent (limits replay of one captured form).
    FORM_MAX_AGE_SECONDS = 60 * 60 * 24

    # Tie the CSRF token to the session instead of expiring it after an hour, so a
    # prospect who leaves the contact page open doesn't lose their enquiry.
    WTF_CSRF_TIME_LIMIT = None

    # Per-IP cap on accepted contact submissions (each costs Make operations). Only
    # submissions that pass validation count, so typos never lock anyone out; mobile
    # carriers share IPs between many users, so keep this generous.
    CONTACT_RATE_LIMIT = "10 per hour;30 per day"
    # Loose per-IP cap on every contact POST, rejected ones included, so bots can't hammer it.
    CONTACT_POST_LIMIT = "60 per hour"
    # Max unsent leads one IP can write to the logs per hour (see routes.may_log_unsent_lead).
    UNSENT_LEAD_LOGS_PER_HOUR = 5
    RATELIMIT_ENABLED = True
    # memory:// is per gunicorn worker and resets on deploy; use redis://... to share it.
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_HEADERS_ENABLED = False

    # Reverse proxies in front of the app (Railway/Render: 1). 0 disables ProxyFix.
    TRUSTED_PROXY_COUNT = int(os.environ.get("TRUSTED_PROXY_COUNT", "1"))

    # Static assets are cache-busted by content hash (see asset_url), so cache aggressively.
    SEND_FILE_MAX_AGE_DEFAULT = 60 * 60 * 24 * 365

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = not DEBUG

    # Only enable once every subdomain of the production domain serves HTTPS.
    HSTS_INCLUDE_SUBDOMAINS = os.environ.get("HSTS_INCLUDE_SUBDOMAINS") == "1"
