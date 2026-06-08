#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

IMAGE_REPO="${IMAGE_REPO:-registry.xzzandzyc.store:5000/project/warehouse-carbon}"
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD)}"
PLATFORM="${PLATFORM:-${PLATFORMS:-linux/amd64}}"
DOCKERFILE="${DOCKERFILE:-tools/deploy/docker/Dockerfile.distroless}"
PUSH_LATEST="${PUSH_LATEST:-true}"
LOCAL_IMAGE_TAG="${LOCAL_IMAGE_TAG:-warehouse-carbon:build-${IMAGE_TAG}}"

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
echo "[INFO] Platform: ${PLATFORM}"
echo "[INFO] Dockerfile: ${DOCKERFILE}"
echo "[INFO] Local image tag: ${LOCAL_IMAGE_TAG}"

if [[ "${PLATFORM}" != "linux/amd64" ]]; then
  echo "[ERROR] This script is intentionally restricted to linux/amd64 for production parity." >&2
  echo "[ERROR] Received PLATFORM=${PLATFORM}" >&2
  exit 1
fi

PRIMARY_REMOTE_TAG="${IMAGE_REPO}:${IMAGE_TAG}"

echo "[INFO] Building local image..."
docker build \
  --platform "${PLATFORM}" \
  --file "${DOCKERFILE}" \
  --tag "${LOCAL_IMAGE_TAG}" \
  .

echo "[INFO] Tagging image for registry..."
docker tag "${LOCAL_IMAGE_TAG}" "${PRIMARY_REMOTE_TAG}"

echo "[INFO] Pushing image: ${PRIMARY_REMOTE_TAG}"
docker push "${PRIMARY_REMOTE_TAG}"

if [[ "${PUSH_LATEST}" == "true" ]]; then
  echo "[INFO] Tagging image as latest..."
  docker tag "${LOCAL_IMAGE_TAG}" "${IMAGE_REPO}:latest"
  echo "[INFO] Pushing image: ${IMAGE_REPO}:latest"
  docker push "${IMAGE_REPO}:latest"
fi

echo
echo "[OK] Image pushed successfully"
echo "  - ${PRIMARY_REMOTE_TAG}"
if [[ "${PUSH_LATEST}" == "true" ]]; then
  echo "  - ${IMAGE_REPO}:latest"
fi
