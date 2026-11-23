# Image for the hourly ELT run (dlt -> dbt), executed as a Cloud Run Job.
# The same image runs in both environments; env vars pick the target:
#   local test: (none)                          -> DuckDB + dbt target "dev"
#   Cloud Run:  DLT_DESTINATION=bigquery, DBT_TARGET=prod

# Base image: Debian slim with Python 3.14 and uv preinstalled.
FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim

# Compile .pyc at install time (faster start), copy files instead of
# hard-linking, keep no uv download cache in the image, stream logs
# without buffering, and put the project's virtualenv first on PATH.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Run as a non-root user. Create it first and own /app up front: a later
# "chown -R" would copy every installed file into a new layer.
RUN useradd --create-home elt \
    && mkdir /app \
    && chown elt:elt /app
USER elt
WORKDIR /app

# 1) Dependencies only. This layer is rebuilt only when the lock file
#    changes, not on every code change.
COPY --chown=elt:elt pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# 2) Application code and non-secret config.
COPY --chown=elt:elt .dlt/config.toml .dlt/config.toml
COPY --chown=elt:elt donkey_pipeline.py ./
COPY --chown=elt:elt donkey_dbt/ donkey_dbt/

# 3) dbt packages are baked into the image, so runs don't depend on dbt Hub.
RUN cd donkey_dbt && dbt deps

# Extract/load, then transform/test. "&&" stops the run if dlt fails, and a
# non-zero exit code marks the Cloud Run execution as failed (and retried).
# dbt is run from donkey_dbt/ so profiles.yml and the relative DuckDB path
# (../donkey.duckdb) resolve correctly.
CMD ["sh", "-c", "python donkey_pipeline.py && cd donkey_dbt && dbt build"]
