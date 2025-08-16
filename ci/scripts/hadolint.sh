#!/usr/bin/env bash
set -eux
DOCKERFILE="${DOCKERFILE:-container/Dockerfile}"
test -f "$DOCKERFILE"
docker run --rm -i hadolint/hadolint < "$DOCKERFILE" || true
