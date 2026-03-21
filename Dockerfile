FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock* ./

# Install dependencies
RUN uv sync --no-dev --no-install-project

# Build-time version info
ARG BUILD_COMMIT=dev
ARG BUILD_VERSION=0.1.0

# Copy application code
COPY . .

# Write version file
RUN echo "{\"version\": \"${BUILD_VERSION}\", \"commit\": \"${BUILD_COMMIT}\"}" > /app/version.json

# Install project
RUN uv sync --no-dev

EXPOSE 8000

CMD ["bash", "start.sh"]
