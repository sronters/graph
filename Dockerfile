FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:0.8.15 /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY graphtrust ./graphtrust
COPY configs ./configs
RUN uv sync --frozen --no-dev --no-editable

RUN adduser --disabled-password --gecos "" graphtrust \
    && mkdir -p /app/data /app/artifacts \
    && chown -R graphtrust:graphtrust /app
USER graphtrust
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["graphtrust", "serve", "--host", "0.0.0.0", "--port", "8000"]
