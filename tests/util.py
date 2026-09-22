import re


def started_token(client, path="/contact", **kwargs):
    """GET the contact form and return its signed render timestamp, as a browser would send it."""
    html = client.get(path, **kwargs).get_data(as_text=True)
    return re.search(r'name="started" type="hidden" value="([^"]+)"', html).group(1)


def form_data(client, data, **kwargs):
    return {**data, "started": started_token(client, **kwargs)}
