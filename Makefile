.PHONY: sync lint format-check typecheck test frontend-quality quality

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

frontend-quality:
	npm --prefix frontend run lint
	npm --prefix frontend run typecheck
	npm --prefix frontend run test
	npm --prefix frontend run build

quality: lint format-check typecheck test frontend-quality
