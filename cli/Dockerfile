FROM python:3.11-slim

ARG VERSION=dev
LABEL org.opencontainers.image.title="sandwalk" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.source="https://github.com/fastfold-ai/sandwalk"

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml README.md ./
COPY src/ src/

# Install the full project (all optional dependencies)
RUN pip install --no-cache-dir ".[all]"

# Persistent config, sessions, skills, and downloaded datasets
RUN mkdir -p /root/.sandwalk/data

VOLUME /root/.sandwalk

ENTRYPOINT ["sandwalk"]
