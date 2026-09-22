import pytest


@pytest.mark.parametrize("path", ["/", "/services", "/how-it-works", "/about", "/contact", "/thanks"])
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
