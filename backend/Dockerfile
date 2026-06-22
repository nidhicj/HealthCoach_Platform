FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first — layer cache on these
COPY pyproject.toml uv.lock ./

# Install production dependencies only (no pytest, ruff, mypy)
RUN uv sync --frozen --no-dev

# Copy application source
COPY src/ src/
COPY prompts/ prompts/
COPY alembic/ alembic/
COPY alembic.ini alembic.ini

# Cloud Run injects PORT; default matches Cloud Run's expected 8080
ENV PORT=8080
EXPOSE 8080

CMD ["uv", "run", "--no-dev", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
