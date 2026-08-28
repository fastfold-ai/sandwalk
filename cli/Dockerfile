FROM python:3.11-slim

ARG VERSION=dev
# Same extras as Agent CLI CI. Skip ml (torch) and singlecell (Census / TileDB) —
# pip 24 backtracks those loose pins into ResolutionTooDeep (~4h, 200k rounds).
# Full science image: docker build --build-arg EXTRAS=all
ARG EXTRAS=chemistry,biology,api

LABEL org.opencontainers.image.title="sandwalk" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.source="https://github.com/fastfold-ai/sandwalk"

WORKDIR /app

ENV UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

COPY --from=ghcr.io/astral-sh/uv:0.8.22 /uv /usr/local/bin/uv

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml README.md uv.lock ./
COPY src/ src/

# Locked extras — never `pip install ".[all]"` (ResolutionTooDeep).
RUN extras=""; \
    IFS=','; \
    for extra in ${EXTRAS}; do extras="$extras --extra $extra"; done; \
    uv sync --frozen --no-dev --no-cache $extras

# Persistent config, sessions, skills, and downloaded datasets
RUN mkdir -p /root/.sandwalk/data

VOLUME /root/.sandwalk

ENTRYPOINT ["sandwalk"]
