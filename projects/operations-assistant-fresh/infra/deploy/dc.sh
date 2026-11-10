#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
files=(-f compose.yml)
# 小规格服务器通过同一入口启用资源上限，备份及发布沿用相同配置。
if [[ "${COMPACT:-0}" == 1 ]]; then files+=(-f compose.compact.yml); fi
exec docker compose --env-file .env.production "${files[@]}" "$@"
