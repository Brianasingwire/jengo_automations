"""content.toml: the words file the site owner edits, and the sections that stay hidden until filled."""

import os

import pytest

from app import create_app
from app.content import ContentError, content_warnings, load_content

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REAL_CONTENT = os.path.join(ROOT, "content.toml")
STATIC = os.path.join(ROOT, "app", "static")

CLIENT = '''
[[clients]]
name = "Acme Logistics"
website = "https://acme.test"
'''

TESTIMONIAL = '''
[[testimonials]]
quote = "They automated our invoicing in two weeks."
name = "Sarah Achieng"
role = "COO"
company = "Acme Logistics"
'''

CASE_STUDY = '''
[[case_studies]]
slug = "acme-invoicing"
title = "Automating invoicing for Acme Logistics"
client = "Acme Logistics"
industry = "Logistics"
location = "Nairobi, Kenya"
summary = "Invoices now go out the day a delivery is confirmed."
challenge = "Invoices were typed up by hand at the end of each week."
solution = "A Make workflow that builds each invoice when the delivery is confirmed."
results = ["Invoices sent same day", "No more end-of-week backlog"]
tools = ["Make", "Xero"]
quote = "We get paid a week sooner."
quote_by = "Sarah Achieng, COO"
'''


def content_with(tmp_path, extra):
    path = tmp_path / "content.toml"
    with open(REAL_CONTENT, encoding="utf-8") as f:
        path.write_text(f.read() + extra, encoding="utf-8")
    return str(path)


def app_with(tmp_path, extra):
    return create_app({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SESSION_COOKIE_SECURE": False,
        "RATELIMIT_ENABLED": False,
        "SITE_URL": "https://jengo.test",
        "CONTENT_PATH": content_with(tmp_path, extra),
    })


def test_real_content_file_loads_without_problems():
    data = load_content(REAL_CONTENT, STATIC)
    assert data["services"] and data["process"] and data["faqs"]


def test_real_content_fits_search_results():
    data = load_content(REAL_CONTENT, STATIC)
    problems = content_warnings(data, "Jengo")
    assert not problems, "Fix these in content.toml:\n  - " + "\n  - ".join(problems)


def test_optional_sections_are_hidden_while_empty(client):
    home = client.get("/").get_data(as_text=True)
    about = client.get("/about").get_data(as_text=True)
    how = client.get("/how-it-works").get_data(as_text=True)
    assert "Trusted by" not in home
    assert "What our clients say" not in home
    assert "/case-studies/" not in home + how
    assert "In our clients&#39; words" not in about


def test_optional_sections_appear_once_filled(tmp_path):
    client = app_with(tmp_path, CLIENT + TESTIMONIAL + CASE_STUDY).test_client()

    home = client.get("/").get_data(as_text=True)
    assert "Trusted by teams in Kampala and beyond" in home
    assert 'href="https://acme.test"' in home
    assert "They automated our invoicing in two weeks." in home
    assert "Sarah Achieng" in home
    assert 'href="/case-studies/acme-invoicing"' in home

    assert "They automated our invoicing" in client.get("/about").get_data(as_text=True)
    assert 'href="/case-studies/acme-invoicing"' in client.get("/how-it-works").get_data(as_text=True)


def test_case_study_page_and_sitemap(tmp_path):
    client = app_with(tmp_path, CASE_STUDY).test_client()
    page = client.get("/case-studies/acme-invoicing")
    html = page.get_data(as_text=True)
    assert page.status_code == 200
    assert "<title>Automating invoicing for Acme Logistics | Jengo</title>" in html
    assert html.count("<h1") == 1
    assert "Invoices sent same day" in html and "We get paid a week sooner." in html
    assert "<loc>https://jengo.test/case-studies/acme-invoicing</loc>" in client.get("/sitemap.xml").get_data(as_text=True)
    assert client.get("/case-studies/does-not-exist").status_code == 404


def test_hidden_entries_stay_off_the_site(tmp_path):
    client = app_with(tmp_path, TESTIMONIAL.replace('company = "Acme Logistics"', 'company = "Acme Logistics"\nhidden = true')).test_client()
    assert "They automated our invoicing" not in client.get("/").get_data(as_text=True)


def test_user_text_is_escaped(tmp_path):
    client = app_with(tmp_path, TESTIMONIAL.replace("They automated", "<script>alert(1)</script> They automated")).test_client()
    html = client.get("/").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_edits_show_up_on_refresh_while_previewing(tmp_path):
    path = content_with(tmp_path, "")
    app = create_app({"DEBUG": True, "SESSION_COOKIE_SECURE": False, "CONTENT_PATH": path})
    client = app.test_client()
    assert "Automate the busywork." in client.get("/").get_data(as_text=True)

    with open(path, encoding="utf-8") as f:
        text = f.read().replace('title_line_1 = "Automate the busywork."', 'title_line_1 = "Automate the boring bits."')
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    os.utime(path, (os.path.getatime(path), os.path.getmtime(path) + 5))
    assert "Automate the boring bits." in client.get("/").get_data(as_text=True)


# --- Mistakes a non-developer might make: each gives a clear message ---------

@pytest.mark.parametrize("extra,message", [
    ('\n[[testimonials]]\nquote = "Great work\nname = "Sam"\n', "can't be read"),
    ('\n[[testimonials]]\nquote = "Great work."\n', "missing `name`"),
    (CASE_STUDY.replace('slug = "acme-invoicing"', 'slug = "Acme Invoicing!"'), "lowercase letters"),
    (CASE_STUDY + CASE_STUDY, "same `slug`"),
    ('\n[[clients]]\nname = "Acme"\nlogo = "acme.svg"\n', "isn't in app/static/img/clients/"),
    # Regression: odd logo paths passed the check, then crashed the home page.
    ('\n[[clients]]\nname = "Acme"\nlogo = "/etc/hostname"\n', "should be just a file name"),
    ('\n[[clients]]\nname = "Acme"\nlogo = "../../config.py"\n', "should be just a file name"),
    # Regression: any link was accepted, including javascript: ones.
    ('\n[[clients]]\nname = "Acme"\nwebsite = "javascript:alert(1)"\n', "must start with https://"),
    ('\n[[clients]]\nname = "Acme"\nwebsite = "acme.com"\n', "must start with https://"),
])
def test_mistakes_are_explained(tmp_path, extra, message):
    with pytest.raises(ContentError, match=message):
        load_content(content_with(tmp_path, extra), STATIC)


def test_unknown_icon_is_explained(tmp_path):
    path = content_with(tmp_path, "")
    with open(path, encoding="utf-8") as f:
        text = f.read().replace('icon = "workflow"', 'icon = "rocket"', 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    with pytest.raises(ContentError, match='unknown icon "rocket"'):
        load_content(path, STATIC)


def test_broken_content_stops_the_site_from_starting(tmp_path):
    with pytest.raises(ContentError):
        app_with(tmp_path, '\n[[testimonials]]\nquote = "unterminated\n')


def test_long_titles_and_descriptions_are_flagged(tmp_path):
    data = load_content(content_with(tmp_path, CASE_STUDY.replace(
        'title = "Automating invoicing for Acme Logistics"',
        'title = "Automating invoicing, payments and reconciliation for Acme Logistics in Nairobi"',
    )), STATIC)
    warnings = content_warnings(data, "Jengo")
    assert any("acme-invoicing" in w and "title" in w for w in warnings)


def test_client_logo_is_shown_when_present(tmp_path):
    logo_dir = os.path.join(STATIC, "img", "clients")
    os.makedirs(logo_dir, exist_ok=True)
    logo = os.path.join(logo_dir, "_test-logo.svg")
    with open(logo, "w") as f:
        f.write('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"></svg>')
    try:
        client = app_with(tmp_path, CLIENT.replace('name = "Acme Logistics"', 'name = "Acme Logistics"\nlogo = "_test-logo.svg"')).test_client()
        html = client.get("/").get_data(as_text=True)
        assert 'alt="Acme Logistics"' in html and "/static/img/clients/_test-logo.svg" in html
    finally:
        os.remove(logo)


def test_contact_preselect_still_works_from_services(client):
    html = client.get("/services").get_data(as_text=True)
    assert 'href="/contact?service=care_plan"' in html


def test_home_sections_alternate_backgrounds(tmp_path):
    """Regression: with testimonials but no case studies, two grey sections touched."""
    import re as _re

    for extra in ("", TESTIMONIAL, CASE_STUDY, TESTIMONIAL + CASE_STUDY):
        html = app_with(tmp_path, extra).test_client().get("/").get_data(as_text=True)
        body = html[html.index("<main"):html.index("</main>")]
        backgrounds = ["grey" if "bg-slate-50" in cls else "white"
                       for cls in _re.findall(r'<section class="section([^"]*)"', body)]
        assert all(a != b for a, b in zip(backgrounds, backgrounds[1:])), (extra[:20], backgrounds)
