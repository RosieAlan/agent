#!/usr/bin/env bash
set -euo pipefail
umask 077
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
user=${1:?Usage: bash create-auth.sh USERNAME}
[[ "$user" =~ ^[a-zA-Z0-9_-]{1,64}$ ]] || exit 2
mkdir -p auth
read -r -s -p 'Gateway password: ' password
printf '\n'
[[ ${#password} -ge 16 ]] || { echo 'Use at least 16 characters'; exit 2; }
hash=$(printf '%s\n' "$password" | openssl passwd -apr1 -stdin)
printf '%s:%s\n' "$user" "$hash" > auth/htpasswd
chmod 644 auth/htpasswd
chmod 755 auth
unset password hash
echo 'Gateway password hash saved'
