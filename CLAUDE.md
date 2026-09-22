# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Marketing site for Jengo, an AI automation agency in Kampala, Uganda, selling to local and East African clients as well as international ones (US, UK, EU, Australia). Copy should address both audiences. Flask + Jinja2 server-rendered pages, Tailwind CSS v4, Alpine.js from CDN for the mobile nav and the form's submit state only. There is no Node or JS build pipeline.

## Commands

```bash
make install     # uv venv (.venv, Python 3.12) + requirements-dev.txt
make dev         # flask dev server with reload on :5000
make css         # rebuild app/static/css/site.css (minified)
make css-watch   # rebuild on template changes
make test        # pytest
.venv/bin/pytest tests/test_contact.py::test_honeypot_is_silently_dropped   # single test
```

Tailwind runs through the `pytailwindcss` standalone CLI (dev dependency; version pinned in the Makefile). **`site.css` is committed and not built on deploy.** After changing classes in templates or `app/*.py`, run `make css` and commit the output. Otherwise production styles will be missing those classes. Sources scanned: `app/templates/**` and `app/*.py` (see `@source` in `app/static/css/input.css`).

## Architecture

- `app/__init__.py`: `create_app(overrides)` factory. Registers CSRF, the `icon()` Jinja global (`app/icons.py`), `asset_url()` (static URL plus content hash for 1-year caching), security headers and error pages. Raises at startup if `SECRET_KEY` is unset outside debug or testing.
- `app/routes.py`: single `main` blueprint. Injects shared copy from `app/content.py` (services, process steps, FAQs, tools) into every template. Records first-touch attribution (UTM parameters, referrer, landing page) in the session. Also serves `robots.txt`, `sitemap.xml` (from `SITEMAP_PAGES`) and `/healthz`.
- `app/content.py`: marketing copy shared between the Home overview and the Services detail page. Edit copy here, not in the templates.
- Security (`app/__init__.py`):
  - `ProxyFix` trusts `TRUSTED_PROXY_COUNT` hops (default 1, for Railway/Render), so `remote_addr` and `is_secure` reflect the real client.
  - Every response gets a CSP with a per-request nonce. **Any inline `<script>` must carry `nonce="{{ csp_nonce }}"`, or the browser blocks it.** JSON-LD blocks are exempt.
  - The CSP allows `'unsafe-eval'` only because Alpine's standard build needs it.
  - HSTS is sent only over HTTPS.
  - The CDN Alpine `<script>` carries an SRI hash. If you bump its version, recompute the hash:
    `curl -s <url> | openssl dgst -sha384 -binary | openssl base64 -A`.
- SEO: every page sets `{% block title %}` and `{% block description %}`. `base.html` builds the canonical URL, Open Graph and Twitter tags, and the JSON-LD from them using `SITE_URL`. Each page has exactly one `<h1>`, and a test enforces this.

### Lead capture (the critical path)

The contact form → `routes.contact` → `leads.build_payload` → `leads.send_lead` → Make.com Custom Webhook (`MAKE_WEBHOOK_URL`). The Make scenario, which scores leads on service type, budget and timeline, is built and maintained separately by the owner, outside this repo.

- The payload is flat JSON: `submission_id, submitted_at, name, email, service_type, service_type_id, budget, budget_id, timeline, timeline_id, message, meta`. Each choice field is sent as both its display label and its stable id. The options are defined in `app/leads.py`.
- **Option ids are the contract with the Make scenario.** Scoring should key on the `*_id` fields. Labels can be reworded freely, but renaming or removing an id breaks scoring silently. Treat id changes as a breaking change to the webhook contract.
- `meta` carries first-touch attribution (`landing_page`, `referrer`, `utm_*`) plus `source` and `page`.
- Spam handling:
  - CSRF (Flask-WTF), a honeypot field `website`, and a minimum fill time (`MIN_FORM_FILL_SECONDS`, measured from the session timestamp set on GET). Spam is redirected to `/thanks` without being sent.
  - Flask-Limiter caps contact POSTs per IP (`CONTACT_RATE_LIMIT`, default 10/hour and 30/day), and returns the 429 page with an email fallback.
  - Limits use `memory://` by default, which is per gunicorn worker and resets on deploy. Set `RATELIMIT_STORAGE_URI=redis://...` for a shared limit.
- If the webhook fails, the user sees an error with the contact email and the full payload is logged at ERROR with the prefix `LEAD PAYLOAD:`, so the lead can be recovered from the host's logs. If `MAKE_WEBHOOK_URL` is unset, the payload is only logged.

## Config / deploy

The environment variables are listed in `.env.example` (`SECRET_KEY`, `MAKE_WEBHOOK_URL`, `SITE_URL`, `CONTACT_EMAIL`, `TRUSTED_PROXY_COUNT`, `RATELIMIT_STORAGE_URI`, `FLASK_DEBUG`). Railway uses the `Procfile`, and Render uses `render.yaml`. Both run `gunicorn wsgi:app`. The health check is `/healthz`.

Tests use `create_app({...})` overrides with CSRF, rate limiting and the fill-time check disabled (see `tests/conftest.py`), and mock `app.leads.requests.post`.

## Review before shipping

The project subagent `code-reviewer` (`.claude/agents/code-reviewer.md`) is a read-only pre-ship check. It covers leaked secrets and personal data, the lead-webhook contract, false or unverified claims in site copy, SEO rules, and whether `site.css` was rebuilt. Run it after changes and before committing or deploying.

The project subagent `security-reviewer` (`.claude/agents/security-reviewer.md`) is a read-only security audit. It covers secrets (including git history), CSRF, XSS, SSRF, abuse of the lead form, personal data in logs, cookies and headers, CDN scripts and dependencies, and deploy config. Run it before every deploy, and after changes to routes, forms, config or dependencies.
