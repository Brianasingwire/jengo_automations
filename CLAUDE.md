# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Marketing site for Jengo, an AI automation agency in Kampala, Uganda, selling to local and East African clients as well as international ones (US, UK, EU, Australia). Copy should address both audiences. Flask + Jinja2 server-rendered pages, Tailwind CSS v4, and one small vanilla script (`app/static/js/site.js`: mobile menu, form submit state, scroll fade-ins). Everything is self-hosted, including the font, so there are no third-party requests. There is no Node or JS build pipeline, and no JS framework: keep it that way, because the CSP forbids `'unsafe-eval'`.

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

- `app/__init__.py`: `create_app(overrides)` factory. `check_production_config` refuses to start outside debug/testing if `SECRET_KEY` or `MAKE_WEBHOOK_URL` is missing, `SITE_URL` is localhost, or `CONTACT_EMAIL` is the `.example` placeholder. It also refuses debug on an https `SITE_URL`, and refuses the public dev fallback key anywhere except a localhost `SITE_URL`. Registers CSRF, the `icon()` Jinja global (`app/icons.py`), `asset_url()` (static URL plus content hash for 1-year caching), security headers and error pages.
- `app/routes.py`: single `main` blueprint. Injects the parsed `content.toml` into every template as `c`. Records first-touch attribution (UTM parameters, referrer, landing page) in the session. Also serves `robots.txt`, `sitemap.xml` (from `SITEMAP_PAGES`) and `/healthz`.
- **All page copy lives in `content.toml`** at the repo root, which the site owner edits directly (it has non-developer instructions at the top). Templates read it as `c` (e.g. `c.home.hero.intro`, `c.services`); never hard-code page copy in a template. Only navigation labels, form questions (`app/forms.py`), dropdown labels (`app/leads.py`) and the privacy policy stay outside it.
  - `app/content.py` loads and validates the file at startup, so a broken file stops the app with a plain-language message instead of going live. It checks TOML syntax, required fields, icon names and case-study slugs. It also checks that client logos are plain image file names that exist, and that client websites start with `http(s)://` (no `javascript:` links). `content_warnings()` flags titles over 52 characters and descriptions over 160; `make test` runs it. In debug, edits are picked up on refresh.
  - `[[clients]]`, `[[testimonials]]` and `[[case_studies]]` are optional: their sections (home, about, how it works) render only when entries exist, and `hidden = true` hides an entry. Each case study gets `/case-studies/<slug>` and a sitemap entry. Client logos go in `app/static/img/clients/`.
  - Avoid TOML keys named `items`, `values`, `keys`, `get` or `update`: in Jinja, `x.items` resolves to the dict method, not the content.
- Security (`app/__init__.py`):
  - `ProxyFix` trusts `TRUSTED_PROXY_COUNT` hops (default 1, for Railway/Render), so `remote_addr` and `is_secure` reflect the real client.
  - Every response gets a CSP with a per-request nonce. **Any inline `<script>` must carry `nonce="{{ csp_nonce }}"`, or the browser blocks it.** JSON-LD blocks are exempt.
  - The CSP is `'self'`-only for scripts, styles and fonts, with no `'unsafe-eval'` or `'unsafe-inline'`. Adding any third-party asset (analytics, embeds, CDN) means deliberately widening the CSP in `app/__init__.py`.
  - The font is a self-hosted Latin subset (`app/static/fonts/`, SIL OFL). The `@font-face` URL in `input.css` must match the `<link rel="preload">` in `base.html` exactly, or the font downloads twice.
  - `ProxyFix` does not trust `X-Forwarded-Host`, because public URLs always come from `SITE_URL`.
  - HSTS is sent only over HTTPS. `HSTS_INCLUDE_SUBDOMAINS=1` adds `includeSubDomains`.
  - The `urllib3` logger is pinned to WARNING, because at DEBUG it logs request URLs, including the webhook URL.
  - `.reveal` sections are hidden by the inline script in `base.html` until `site.js` fades them in. If `site.js` hasn't set `window.jengoSiteJs` within 2.5 seconds, the inline script un-hides them. Tailwind scans `app/static/js` too, so classes toggled in `site.js` get built.
- SEO: every page sets `{% block title %}` and `{% block description %}`. `base.html` builds the canonical URL, Open Graph and Twitter tags, and the JSON-LD from them using `SITE_URL`. Each page has exactly one `<h1>`, and a test enforces this.

### Lead capture (the critical path)

The contact form → `routes.contact` → `leads.build_payload` → `leads.send_lead` → Make.com Custom Webhook (`MAKE_WEBHOOK_URL`). The Make scenario, which scores leads on service type, budget and timeline, is built and maintained separately by the owner, outside this repo.

- The payload is flat JSON: `submission_id, submitted_at, name, email, service_type, service_type_id, budget, budget_id, timeline, timeline_id, message, meta`. Each choice field is sent as both its display label and its stable id. The options are defined in `app/leads.py`.
- **Option ids are the contract with the Make scenario.** Scoring should key on the `*_id` fields. Labels can be reworded freely, but renaming or removing an id breaks scoring silently. Treat id changes as a breaking change to the webhook contract.
- `meta` carries first-touch attribution (`landing_page`, `referrer`, `utm_*`) plus `source` and `page`.
- Spam handling:
  - CSRF (Flask-WTF). `WTF_CSRF_TIME_LIMIT = None` ties the token to the session instead of expiring it after an hour. `/contact` is `@csrf.exempt` from the global check and calls `csrf.protect()` inside the view instead: Flask-Limiter applies route limits inside the view, so this order is what makes rejected POSTs count towards `CONTACT_POST_LIMIT`. Don't remove the exempt without moving the check. A failed check re-shows the filled-in form, keeping the visitor's original `started` token (never issue a pre-aged one there, since bots could harvest it), with a "press Send again" message. It never shows a bare 400.
  - A honeypot field `website`.
  - A minimum fill time and single-use forms. The hidden field `started` carries a signed `[render time, one-time id]` (itsdangerous, keyed on `SECRET_KEY`). `routes.human_form_age()` is the single "does this look like a person?" check: empty honeypot, valid unused token, and at least `MIN_FORM_FILL_SECONDS` old. Accepted forms have their id recorded in the session, so a captured form can't be replayed. Forms older than `FORM_MAX_AGE_SECONDS` are re-shown for confirmation. Re-rendered forms keep the original token.
  - Spam is redirected to `/thanks` without being sent.
  - Flask-Limiter caps accepted contact submissions per IP (`CONTACT_RATE_LIMIT`, default 10/hour and 30/day; only 302 responses count, so validation errors never use up the allowance), plus a looser cap on every POST (`CONTACT_POST_LIMIT`, 60/hour) so bots can't hammer the form. Over a limit, the visitor gets the 429 page with an email fallback.
  - Limits use `memory://` by default, which is per gunicorn worker and resets on deploy. Set `RATELIMIT_STORAGE_URI=redis://...` for a shared limit.
- Any lead that doesn't reach Make is logged at ERROR via `leads.log_unsent_lead` with the prefix `LEAD PAYLOAD:`, so it can be recovered from the host's logs. This covers webhook failure, a CSRF failure, hitting the rate limit and a form left open too long. The CSRF, rate-limit and too-old paths only log when `human_form_age()` passes and `may_log_unsent_lead()` allows it (`UNSENT_LEAD_LOGS_PER_HOUR` per IP), so bots can't flood the logs with fake leads. The privacy page discloses this logging. **Never log `str(exc)` from requests: it contains the webhook URL, which is a credential.** In local dev without `MAKE_WEBHOOK_URL`, leads are only logged.
- Privacy: `/privacy` describes exactly what the code collects and who processes it. If you change the payload, attribution, cookies or the tools in the pipeline, update that page too.

## Config / deploy

The environment variables are listed in `.env.example` (`SECRET_KEY`, `MAKE_WEBHOOK_URL`, `SITE_URL`, `CONTACT_EMAIL`, `TRUSTED_PROXY_COUNT`, `RATELIMIT_STORAGE_URI`, `HSTS_INCLUDE_SUBDOMAINS`, `FLASK_DEBUG`). The first four are required in production. Railway uses the `Procfile`, and Render uses `render.yaml`. Both run `gunicorn wsgi:app`. The health check is `/healthz`.

Tests use `create_app({...})` overrides with CSRF and rate limiting disabled and `MIN_FORM_FILL_SECONDS=0` (see `tests/conftest.py`), and mock `app.leads.requests.post`. Contact POSTs need a signed `started` value: use `tests.util.form_data(client, data)`, which GETs the form first like a browser would. `test_option_ids_are_pinned` pins the webhook contract.

## Review before shipping

The project subagent `code-reviewer` (`.claude/agents/code-reviewer.md`) is a read-only pre-ship check. It covers leaked secrets and personal data, the lead-webhook contract, false or unverified claims in site copy (including `content.toml`), SEO rules, and whether `site.css` was rebuilt. Run it after changes and before committing or deploying.

The project subagent `security-reviewer` (`.claude/agents/security-reviewer.md`) is a read-only security audit. It covers secrets (including git history), CSRF, XSS, SSRF, abuse of the lead form, personal data in logs, cookies and headers, CDN scripts and dependencies, and deploy config. Run it before every deploy, and after changes to routes, forms, config or dependencies.
