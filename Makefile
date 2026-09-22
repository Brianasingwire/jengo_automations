TAILWINDCSS_VERSION ?= v4.3.3
export TAILWINDCSS_VERSION
TW = .venv/bin/tailwindcss -i app/static/css/input.css -o app/static/css/site.css

.PHONY: install dev css css-watch test

install:
	uv venv --python 3.12 .venv
	uv pip install --python .venv -r requirements-dev.txt

dev:
	FLASK_DEBUG=1 .venv/bin/flask --app wsgi run

css:
	$(TW) --minify

css-watch:
	$(TW) --watch

test:
	.venv/bin/pytest -q
