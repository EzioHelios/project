# =============================================================================
# Production Python Container
# =============================================================================
# This Dockerfile creates a secure, optimized container for production.
#
# Security features:
# - Multi-stage build to minimize attack surface
# - Non-root user execution (UID 65532)
# - Minimal runtime dependencies
# - No unnecessary build tools in final image
#
# Optimization features:
# - Cache mounts for faster rebuilds
# - Bind mounts for dependency layer caching
# - Bytecode compilation for faster startup
#
# Build: docker build -t app:latest .
# =============================================================================

# -----------------------------------------------------------------------------
# Build Arguments
# -----------------------------------------------------------------------------
ARG PYTHON_VERSION=3.13
ARG DEBIAN_VERSION=bookworm
ARG BUILDER_IMAGE=python:${PYTHON_VERSION}-slim-${DEBIAN_VERSION}
ARG DEBIAN_MIRROR=mirrors.aliyun.com

# =============================================================================
# Stage 1: Python Base
# =============================================================================
# Minimal base image with essential runtime dependencies
# =============================================================================
FROM ${BUILDER_IMAGE} AS python-base

ARG DEBIAN_MIRROR

RUN sed -i "s|http://|https://|g; s|deb.debian.org|${DEBIAN_MIRROR}|g; s|security.debian.org|${DEBIAN_MIRROR}|g" /etc/apt/sources.list.d/debian.sources

RUN --mount=type=cache,id=apt-cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,id=apt-lib,target=/var/lib/apt,sharing=locked \
    apt-get -o Acquire::Retries=5 update \
    && apt-get -o Acquire::Retries=5 upgrade -y \
    && apt-get -o Acquire::Retries=5 install -y --fix-missing --no-install-recommends \
        tini \
        ca-certificates \
    && rm -rf /var/log/* /tmp/* \
    && mkdir -p /workspace/app

# Install uv (fast Python package installer)
# Pin to specific version for reproducible builds
# For SHA256 pinning: COPY --from=ghcr.io/astral-sh/uv@sha256:<digest> /uv /uvx /bin/
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Pin Bun to the version validated by the local toolchain. Floating `latest`
# introduced a Bun 1.4 incompatibility in the OpenAPI type-generation step.
COPY --from=oven/bun:1.3.10 /usr/local/bin/bun /usr/local/bin/bun
COPY --from=oven/bun:1.3.10 /usr/local/bin/bunx /usr/local/bin/bunx

# =============================================================================
# Stage 2: Builder
# =============================================================================
# Installs all dependencies and builds the application
# =============================================================================
FROM python-base AS builder

ARG UV_INSTALL_ARGS="--no-dev"

# Environment configuration for optimal builds
ENV GRPC_PYTHON_BUILD_WITH_CYTHON=1 \
    BUN_CONFIG_NO_PROGRESS=1 \
    BUN_INSTALL_CACHE_DIR=/root/.bun/install/cache \
    BUN_RUNTIME_TRANSPILER_CACHE_PATH=/root/.bun/transpiler-cache \
    CI=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_SYSTEM_PYTHON=1 \
    PATH="/workspace/app/.venv/bin:/usr/local/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# Install build dependencies
RUN --mount=type=cache,id=apt-cache-builder,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,id=apt-lib-builder,target=/var/lib/apt,sharing=locked \
    apt-get -o Acquire::Retries=5 update \
    && apt-get -o Acquire::Retries=5 install -y --fix-missing --no-install-recommends \
        build-essential \
        curl \
        git \
    && rm -rf /var/log/* /tmp/* \
    && mkdir -p /cloudsql

WORKDIR /workspace/app

# Copy dependency files first (better layer caching)
COPY pyproject.toml uv.lock README.md ./
COPY src/js/web/package.json src/js/web/bun.lock ./src/js/web/
COPY src/js/web/.litestar.json src/js/web/biome.json src/js/web/openapi-ts.config.ts src/js/web/vite.config.ts src/js/web/tsconfig.json ./src/js/web/
COPY src/js/templates/package.json src/js/templates/bun.lock ./src/js/templates/

# Install JavaScript dependencies for web app
WORKDIR /workspace/app/src/js/web
RUN --mount=type=cache,id=bun-install-cache,target=/root/.bun/install/cache,sharing=locked \
    --mount=type=cache,id=bun-transpiler-cache,target=/root/.bun/transpiler-cache,sharing=locked \
    bun install --frozen-lockfile

# Install JavaScript dependencies for email templates
WORKDIR /workspace/app/src/js/templates
RUN --mount=type=cache,id=bun-install-cache,target=/root/.bun/install/cache,sharing=locked \
    --mount=type=cache,id=bun-transpiler-cache,target=/root/.bun/transpiler-cache,sharing=locked \
    bun install --frozen-lockfile
WORKDIR /workspace/app

# Create virtual environment and install Python dependencies
# Using cache mounts for faster rebuilds
RUN --mount=type=cache,id=uv-cache,target=/root/.cache/uv \
    uv venv \
    && uv sync ${UV_INSTALL_ARGS} --frozen --no-install-project --no-editable \
    && uv export ${UV_INSTALL_ARGS} --frozen --no-hashes --no-emit-project --output-file=requirements.txt

# Copy application source
COPY tools ./tools/
COPY src/js/web/ ./src/js/web/
COPY src/js/templates/ ./src/js/templates/
COPY src/py/ ./src/py/

# Create required directories
RUN mkdir -p src/py/app/server/static/web src/py/app/server/static/email

# Build email templates (must be before wheel build to include in package)
RUN --mount=type=cache,id=bun-transpiler-cache,target=/root/.bun/transpiler-cache,sharing=locked \
    cd src/js/templates && bun run build

# Generate frontend types separately so failures are isolated and the step can cache independently.
RUN --mount=type=cache,id=uv-cache,target=/root/.cache/uv \
    uv run app assets generate-types

# Build frontend assets and create wheel
RUN --mount=type=cache,id=uv-cache,target=/root/.cache/uv \
    --mount=type=cache,id=bun-transpiler-cache,target=/root/.bun/transpiler-cache,sharing=locked \
    (cd src/js/web && bun run build) \
    && uv sync ${UV_INSTALL_ARGS} --frozen --no-editable \
    && uv build

# =============================================================================
# Stage 3: Runtime
# =============================================================================
# Minimal production image with only runtime dependencies
# =============================================================================
FROM python-base AS runtime

ARG LITESTAR_APP="app.server.asgi:create_app"

ENV PATH="/workspace/app/.venv/bin:/usr/local/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    LITESTAR_APP="${LITESTAR_APP}"

# Create non-root user
RUN groupadd --system --gid 65532 nonroot \
    && useradd --no-create-home --system --uid 65532 --gid 65532 nonroot \
    && mkdir -p /workspace/app \
    && chown -R nonroot:nonroot /workspace

# Copy cloudsql directory for GCP deployments
COPY --from=builder --chown=65532:65532 /cloudsql /cloudsql

# Copy the built application package explicitly because the wheel install
# currently leaves only dist-info metadata in the runtime image.
COPY --from=builder --chown=65532:65532 /workspace/app/src/py/app /workspace/app/app

# Copy wheel and install
COPY --from=builder --chown=65532:65532 /workspace/app/dist/*.whl /tmp/

WORKDIR /workspace/app

RUN --mount=type=cache,id=uv-cache,target=/root/.cache/uv \
    uv pip install --system --quiet --disable-pip-version-check --no-cache-dir /tmp/*.whl \
    && rm -rf /tmp/* \
    && chown -R nonroot:nonroot /workspace/app

# Switch to non-root user
USER nonroot

# Container configuration
STOPSIGNAL SIGTERM
EXPOSE 8000

ENTRYPOINT ["tini", "--"]
CMD ["granian", "--interface", "asgi", "--factory", "app.server.asgi:create_app", "--host", "0.0.0.0", "--port", "8000"]

# Labels for container metadata (OCI spec)
LABEL org.opencontainers.image.title="Litestar Fullstack SPA" \
      org.opencontainers.image.description="Python application container" \
      org.opencontainers.image.vendor="Litestar" \
      org.opencontainers.image.licenses="MIT"
