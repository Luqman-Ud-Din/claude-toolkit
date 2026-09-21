#!/usr/bin/env bash
# Persist the installed core path for subsequent Claude Code Bash commands.
set -euo pipefail
[[ -n "${CLAUDE_ENV_FILE:-}" ]] || exit 0
[[ -n "${CLAUDE_PLUGIN_ROOT:-}" ]] || exit 0
root="$CLAUDE_PLUGIN_ROOT"
# Native Windows Python needs a drive path, not Git Bash's /c/... spelling.
if command -v cygpath >/dev/null 2>&1; then
    root=$(cygpath -m "$root")
fi
printf 'export AUDIT_CORE_ROOT=%q\n' "$root" >> "$CLAUDE_ENV_FILE"
