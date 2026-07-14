.PHONY: sync lint format-check typecheck test quality

sync:
	uv sync --all-extras

lint:
	uv run ruff check .

format-check:
	uv run ruff format --check .

typecheck:
	uv run mypy graphtrust

test:
	uv run pytest -m "not performance" --cov=graphtrust --cov-report=term-missing

quality: lint format-check typecheck test
