# FOOTBALL OS core API — the Python canon itself.
# Build context: apps/api (this directory).
# Runs one door on :8100; migrations apply on boot; the lifespan seeds the catalogs.
# No system packages: psycopg2-binary ships its own libpq, and the healthcheck uses the
# interpreter that is certainly in the image.

FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    SERVICE_PORT=8100 \
    SERVICE_NAME=football-core

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# The source of truth: the unmodified application tree and its migrations.
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./
COPY evals ./evals
COPY seed.py ./

EXPOSE 8100

# Migrations apply before uvicorn binds: a fresh container converges the schema on first boot.
CMD ["sh", "-c", "python -m alembic upgrade head && python -m uvicorn app.main:app --host 0.0.0.0 --port 8100"]

HEALTHCHECK --interval=15s --timeout=5s --retries=12 --start-period=60s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8100/healthz', timeout=5)" || exit 1
