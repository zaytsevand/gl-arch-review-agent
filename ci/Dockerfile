# Stage 1: Build — install adr-agent with all dependencies
FROM python:3.11-slim AS builder

WORKDIR /build
COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir --prefix=/install .

# Stage 2: Runtime — slim image with only the installed package
FROM python:3.11-slim

COPY --from=builder /install /usr/local

# Verify the CLI is available
RUN adr-agent --help > /dev/null 2>&1

# Git is needed for clone, blame, commit, push operations
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["adr-agent"]
