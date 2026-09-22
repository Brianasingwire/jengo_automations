"""Loads and checks the site's words from content.toml (see the notes at the top of that file).

The file is edited by non-developers, so every check explains the problem in plain
language and names the entry to fix.
"""

import os
import re
import tomllib

from .icons import ICONS

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# Plain image file names only: no folders, so a logo can't point anywhere else on disk.
LOGO_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._-]*\.(?:svg|png|webp|jpe?g)$")

# Optional entries: their sections stay hidden on the site while these lists are empty.
OPTIONAL_LISTS = ("clients", "testimonials", "case_studies")

REQUIRED = {
    "services": ("id", "icon", "name", "summary", "description", "examples", "tools", "timeline"),
    "process": ("name", "duration", "body"),
    "faqs": ("question", "answer"),
    "clients": ("name",),
    "testimonials": ("quote", "name"),
    "case_studies": ("slug", "title", "client", "summary", "challenge", "solution", "results"),
}

SECTIONS = ("site", "cta", "home", "services_page", "how_it_works", "case_study_page", "about", "contact", "thanks")


class ContentError(Exception):
    """content.toml has a mistake. The message says what and where."""


def load_content(path, static_folder):
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        raise ContentError(f"The words file is missing: {path}") from None
    except tomllib.TOMLDecodeError as exc:
        raise ContentError(
            f"content.toml can't be read: {exc}. Look for a missing quote mark, comma or "
            "bracket on or just before that line."
        ) from None

    for name in OPTIONAL_LISTS:
        data[name] = [entry for entry in data.get(name, []) if not entry.get("hidden")]

    _check(data, static_folder)
    return data


def _check(data, static_folder):
    problems = [f"the [{section}] section is missing" for section in SECTIONS if section not in data]

    for name, fields in REQUIRED.items():
        for i, entry in enumerate(data.get(name, []), start=1):
            label = entry.get("name") or entry.get("title") or entry.get("slug") or "no name"
            problems += [f"[[{name}]] entry {i} ({label}) is missing `{f}`" for f in fields if not entry.get(f)]

    for entry, where in _entries_with_icons(data):
        if entry.get("icon") not in ICONS:
            problems.append(
                f"unknown icon \"{entry.get('icon')}\" in {where}. "
                "Use one of the names listed at the top of content.toml"
            )

    ids = [s.get("id") for s in data.get("services", [])]
    if len(ids) != len(set(ids)):
        problems.append("two [[services]] entries share the same `id`")

    slugs = [c.get("slug") for c in data["case_studies"]]
    for slug in slugs:
        if slug and not SLUG_RE.match(slug):
            problems.append(
                f"case study slug \"{slug}\" must be lowercase letters, numbers and hyphens only "
                "(e.g. \"coffee-order-intake\")"
            )
    if len(slugs) != len(set(slugs)):
        problems.append("two [[case_studies]] entries share the same `slug`")

    for client in data["clients"]:
        name = client.get("name")
        logo = client.get("logo")
        if logo and not LOGO_RE.match(logo):
            problems.append(
                f"logo \"{logo}\" for client \"{name}\" should be just a file name like \"acme.svg\" "
                "(an .svg, .png, .webp or .jpg in app/static/img/clients/)"
            )
        elif logo and not os.path.isfile(os.path.join(static_folder, "img", "clients", logo)):
            problems.append(f"logo \"{logo}\" for client \"{name}\" isn't in app/static/img/clients/")
        website = client.get("website")
        if website and not re.match(r"^https?://[^\s\"'<>]+$", website):
            problems.append(f"website \"{website}\" for client \"{name}\" must start with https:// (or http://)")

    if problems:
        raise ContentError("content.toml needs fixing:\n  - " + "\n  - ".join(problems))


def _entries_with_icons(data):
    for s in data.get("services", []):
        yield s, f"[[services]] \"{s.get('name')}\""
    home = data.get("home", {})
    for step in home.get("hero_example", {}).get("steps", []):
        yield step, "[[home.hero_example.steps]]"
    for card in home.get("why", {}).get("cards", []):
        yield card, "[[home.why.cards]]"
    for step in data.get("how_it_works", {}).get("pipeline", {}).get("steps", []):
        yield step, "[[how_it_works.pipeline.steps]]"
    for principle in data.get("about", {}).get("principles", []):
        yield principle, "[[about.principles]]"


TITLE_SUFFIX = " | {site_name}"
MAX_TITLE = 60
MAX_DESCRIPTION = 160
PAGES_WITH_META = ("services_page", "how_it_works", "about", "contact")


def content_warnings(data, site_name):
    """Things that don't break the site but hurt search results. Checked by `make test`."""
    suffix = len(TITLE_SUFFIX.format(site_name=site_name))
    warnings = []

    def check(label, title=None, description=None):
        if title and len(title) + suffix > MAX_TITLE:
            warnings.append(
                f"{label} title is {len(title)} characters; keep it to {MAX_TITLE - suffix} "
                f"or Google will cut it off: \"{title}\""
            )
        if description and len(description) > MAX_DESCRIPTION:
            warnings.append(
                f"{label} description is {len(description)} characters; keep it to {MAX_DESCRIPTION}: "
                f"\"{description[:60]}...\""
            )

    home_title = data["site"].get("home_title", "")
    if len(home_title) > MAX_TITLE:
        warnings.append(f"[site] home_title is {len(home_title)} characters; keep it to {MAX_TITLE}")
    check("[home]", description=data["home"].get("description"))
    for page in PAGES_WITH_META:
        check(f"[{page}]", data[page].get("title"), data[page].get("description"))
    for study in data["case_studies"]:
        check(f"case study \"{study.get('slug')}\"", study.get("title"), study.get("summary"))
    return warnings
