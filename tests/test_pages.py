import html as html_lib
import re

import pytest

PUBLIC_PAGES = ["/", "/services", "/how-it-works", "/about", "/contact", "/privacy"]


@pytest.mark.parametrize("path", PUBLIC_PAGES + ["/thanks"])
def test_pages_render_with_seo_tags(client, path):
    resp = client.get(path)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "<title>" in html
    assert '<meta name="description" content="' in html
    assert f'<link rel="canonical" href="https://jengo.test{path}">' in html
    assert html.count("<h1") == 1


def test_404(client):
    assert client.get("/does-not-exist").status_code == 404


def test_sitemap_uses_site_url(client):
    xml = client.get("/sitemap.xml").get_data(as_text=True)
    assert "<loc>https://jengo.test/services</loc>" in xml
    assert "/thanks" not in xml


def test_robots_points_to_sitemap(client):
    body = client.get("/robots.txt").get_data(as_text=True)
    assert "Sitemap: https://jengo.test/sitemap.xml" in body


def test_service_query_preselects_option(client):
    html = client.get("/contact?service=document_ai").get_data(as_text=True)
    assert '<option selected value="document_ai">' in html


@pytest.mark.parametrize("path", PUBLIC_PAGES)
def test_titles_and_descriptions_fit_search_results(client, path):
    page = client.get(path).get_data(as_text=True)
    title = html_lib.unescape(re.search(r"<title>(.*?)</title>", page).group(1))
    description = html_lib.unescape(re.search(r'<meta name="description" content="(.*?)">', page).group(1))
    assert len(title) <= 60, title
    assert 50 <= len(description) <= 160, description


def test_every_public_page_is_in_the_sitemap(client):
    xml = client.get("/sitemap.xml").get_data(as_text=True)
    for path in PUBLIC_PAGES:
        assert f"<loc>https://jengo.test{path}</loc>" in xml


def test_privacy_policy_is_linked_from_footer_and_form(client):
    assert 'href="/privacy"' in client.get("/").get_data(as_text=True)
    contact = client.get("/contact").get_data(as_text=True)
    assert contact.count('href="/privacy"') == 2  # footer + form notice
