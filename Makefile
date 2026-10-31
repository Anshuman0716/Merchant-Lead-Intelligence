.PHONY: setup crawl pipeline app test lint fmt

# Create the virtualenv and install everything (dev + browser extras)
setup:
	uv sync --all-extras --all-groups
	uv run playwright install chromium

# Only the crawl stage (slow, network). Add ARGS=--refresh to ignore the cache.
crawl:
	uv run python -m leadintel.run --only crawl $(ARGS)

# Rebuild everything from raw inputs
pipeline:
	uv run python -m leadintel.run $(ARGS)

app:
	uv run streamlit run app/Home.py

test:
	uv run pytest -q

lint:
	uv run ruff check src tests app

fmt:
	uv run ruff format src tests app
