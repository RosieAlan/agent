#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
tag=${1:?Usage: bash release.sh NEW_IMMUTABLE_TAG PREVIOUS_TAG_OR_first}
previous=${2:?Supply previous tag or first}
[[ "$tag" =~ ^[a-zA-Z0-9][a-zA-Z0-9_.-]{5,100}$ && "$tag" != latest ]] || exit 2
[[ "$previous" =~ ^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,100}$ && "$previous" != latest ]] || exit 2
export RELEASE_TAG="$tag"
bash dc.sh config --quiet
bash dc.sh build api gateway
if bash dc.sh up -d --no-build --wait --wait-timeout 180 api worker gateway; then
  printf 'Release healthy: %s\n' "$tag"
else
  if [[ "$previous" != first ]]; then
    export RELEASE_TAG="$previous"
    bash dc.sh up -d --no-build --wait --wait-timeout 180 api worker gateway
    printf 'Previous release restored: %s\n' "$previous"
  fi
  exit 1
fi
