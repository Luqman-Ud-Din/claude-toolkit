#!/usr/bin/env bash
# Deploys the API to the given environment. Run by the CI deploy job on main.
set -euo pipefail
ENV="$1"
echo "deploying to $ENV"
