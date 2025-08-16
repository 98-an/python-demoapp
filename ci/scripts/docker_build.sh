#!/usr/bin/env bash
set -eux
DOCKERFILE="${DOCKERFILE:-container/Dockerfile}"
IMAGE_REPO="${IMAGE_REPO:-ghcr.io/98-an/python-demoapp}"
SHORT_SHA="${SHORT_SHA:-local}"
docker build -f "$DOCKERFILE" -t "$IMAGE_REPO:$SHORT_SHA" .
docker tag "$IMAGE_REPO:$SHORT_SHA" "$IMAGE_REPO:latest"
