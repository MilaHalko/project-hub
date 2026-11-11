FROM python:3.13-slim AS build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN pip install poetry==2.5.1

WORKDIR /app

# Dependency layer: rebuilt only when the lock file or project metadata change.
COPY pyproject.toml poetry.lock poetry.toml README.md ./
RUN poetry install --only main --no-root --no-interaction

# Install the package itself (editable, pointing at /app/src).
COPY src ./src
RUN poetry install --only main --no-interaction


FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

RUN useradd --create-home --uid 1000 app

WORKDIR /app

# Same paths as in the build stage: the editable install points at /app/src.
COPY --from=build /app/.venv /app/.venv
COPY --from=build /app/src /app/src

USER app

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]

CMD ["uvicorn", "project_hub.main:app", "--host", "0.0.0.0", "--port", "8000"]
