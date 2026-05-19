#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

IMAGE_REPO="${IMAGE_REPO:-registry.xzzandzyc.store:5000/project/warehouse-carbon}"
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD)}"
PLATFORMS="${PLATFORMS:-linux/amd64}"
BUILDER_NAME="${BUILDER_NAME:-multiarch-builder}"
DOCKERFILE="${DOCKERFILE:-tools/deploy/docker/Dockerfile.distroless}"
PUSH_LATEST="${PUSH_LATEST:-true}"

if ! command -v docker >/dev/null 2>&1; then
  echo "[ERROR] docker command not found" >&2
  exit 127
fi

if ! docker info >/dev/null 2>&1; then
  echo "[ERROR] docker daemon is not available" >&2
  exit 1
fi

echo "[INFO] Root directory: ${ROOT_DIR}"
echo "[INFO] Image repo: ${IMAGE_REPO}"
echo "[INFO] Image tag: ${IMAGE_TAG}"
echo "[INFO] Platforms: ${PLATFORMS}"
echo "[INFO] Dockerfile: ${DOCKERFILE}"

if ! docker buildx inspect "${BUILDER_NAME}" >/dev/null 2>&1; then
  echo "[INFO] Creating docker buildx builder: ${BUILDER_NAME}"
  docker buildx create --name "${BUILDER_NAME}" --use
else
  echo "[INFO] Using docker buildx builder: ${BUILDER_NAME}"
  docker buildx use "${BUILDER_NAME}"
fi

TAGS=(--tag "${IMAGE_REPO}:${IMAGE_TAG}")
if [[ "${PUSH_LATEST}" == "true" ]]; then
  TAGS+=(--tag "${IMAGE_REPO}:latest")
fi

echo "[INFO] Building and pushing image..."
docker buildx build \
  --platform "${PLATFORMS}" \
  --file "${DOCKERFILE}" \
  "${TAGS[@]}" \
  --push \
  .

echo
echo "[OK] Image pushed successfully"
echo "  - ${IMAGE_REPO}:${IMAGE_TAG}"
if [[ "${PUSH_LATEST}" == "true" ]]; then
  echo "  - ${IMAGE_REPO}:latest"
fi
