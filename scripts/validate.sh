#!/usr/bin/env bash
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if command -v python3 >/dev/null 2>&1; then python=python3; else python=python; fi
exec "$python" "$here/marketplace.py" validate "$@"
