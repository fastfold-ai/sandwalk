FROM python:3.11-slim

ARG VERSION=dev
LABEL org.opencontainers.image.title="fastfold-agent-cli" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.source="https://github.com/fastfold-ai/fastfold-agent-cli"

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
RUN mkdir -p /root/.fastfold-cli/data

VOLUME /root/.fastfold-cli

ENTRYPOINT ["fastfold"]
