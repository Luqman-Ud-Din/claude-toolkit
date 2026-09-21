---
name: audit-secrets-and-config
description: Scans code, config files, container/CI files, and full git history for hard-coded secrets (API keys, connection strings, JWT signing keys, passwords, certificates, private keys) and reviews production configuration - secrets loaded from env/secret manager not literals, debug/developer pages disabled, production environment flag set, HTTPS/HSTS enforced, and CORS restricted to explicit origins with no wildcard-plus-credentials. Use it whenever the user asks about secrets, credentials, hard-coded keys, leaked keys, config review, environment settings, config files, appsettings, .env, CORS, debug flags, or as part of any security or production-readiness audit - even when the user does not name this skill. Wraps whatever secret scanner is available (candidates listed in references) and produces findings, a table of every config key with its source, and a list of commits containing secrets to purge.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-app:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit secrets and config

Committed secrets and loose production configuration are among the easiest wins
for an attacker and among the most common findings. This skill looks in three
places - the working tree, the configuration surface, and the full git history -
and answers two questions: is anything secret hard-coded, and is production
configured to be safe (no debug pages, prod flag set, HTTPS/HSTS on, CORS locked
down).

**Read-only rule:** never modify the audited code. Write only under `audit/`. The
git-history scan reads history through `audit-git-history` (read-only `git log`); it never rewrites it.
Purging and rotation are remediation steps you recommend, not actions you take.

## Inputs and prerequisites

- The repository to audit (ideally a real git clone so history can be scanned).
- Optional: a dedicated scanner on PATH (gitleaks/trufflehog/detect-secrets); the
  skill uses it if present, else falls back to the bundled script.
- `audit/stack.json` if the orchestrator wrote one; otherwise this skill detects
  the stack.
- Skills from the `audit-core` plugin (reached via `$AUDIT_CORE_ROOT`, exported by that plugin; a sibling `skills/` layout also works): `audit-stack-detection`,
  `audit-code-scan` (grep pass and the shared file walker), `audit-sensitive-data-catalog`
  (secret key names, secret value formats and placeholders), `audit-git-history` (lines
  added per commit) and `audit-finding-writer` (findings I/O).

## Workflow

### 1. Resolve the stack
Run `python "$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py" <repo>`. Open the matching
`references/<stack>.md` (backend for config hardening; the frontend file tells you
which client values are public-by-design and must not be flagged). Keep
`references/tool-candidates.md` open for scanner invocations.

### 2. Automated pass
- **Working tree + patterns:**
  `python "$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py" <repo> --patterns scripts/patterns/<stack>.json --out audit/evidence/audit-secrets-and-config/hits.json`.
- **Git history:**
  `python scripts/git_secret_scan.py <repo> --out audit/evidence/audit-secrets-and-config/history.json --md audit/evidence/audit-secrets-and-config/history.md`
  (add `--include-tree` when the target is not a git checkout). Copy its
  `not_checked` entries (no history, shallow clone) into Not checked. If a dedicated
  scanner is installed, run it too (see `references/tool-candidates.md`) and merge
  results - `trufflehog --only-verified` confirms live secrets.
- **Config key inventory:**
  `python scripts/config_key_inventory.py <repo> --out audit/evidence/audit-secrets-and-config/keys.json --md audit/evidence/audit-secrets-and-config/keys.md`.
  This builds the required "config key -> source (file/env/secret manager)" table
  and flags keys with a literal secret value in a committed file.

### 3. Manual trace of the highest-risk items
1. Every literal-secret candidate - open the file, confirm it is a real, current
   secret (not a placeholder/example) and whether it is in history too.
2. Production config file(s) - `DEBUG`/`DetailedErrors`/log level, the prod
   environment flag, HTTPS/HSTS, secure-cookie flags.
3. CORS configuration - a wildcard or reflected origin combined with credentials
   is the dangerous pattern; explicit origins + credentials is fine.
4. `.gitignore` - is `.env` ignored, and did a real `.env`/keystore slip in?
5. For each confirmed history secret, record the commit(s) for the purge list.

### 4. Write findings
`python "$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py" init audit-secrets-and-config`, then for each
confirmed issue write the finding block (below), save to a temp JSON, and
`python "$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py" add audit/findings/audit-secrets-and-config.json --from <finding.json>`.
Regenerate the report body with
`python "$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py" md audit/findings/audit-secrets-and-config.json --out audit/reports/audit-secrets-and-config.md`,
then prepend the config-key table and the commits-to-purge list from the template
below. De-duplicate the same secret appearing across environments/commits into one
finding with multiple locations (`root_cause_key`). Messy raw scanner lines can go
through `audit-finding-writer`.

### 5. Record what was NOT checked
Add gaps to `scope.not_checked`: history not scanned (shallow clone / not a git
repo), scanner not installed, external secret-manager contents (only references
verified, not values), runtime env vars set outside the repo, binary keystores, and the
folders the shared walker skips (`repo_walk.SKIP_DIRS` in `audit-code-scan`).
Write `audit/status/audit-secrets-and-config.json`
(`{"skill":"audit-secrets-and-config","status":"completed|failed|skipped","reason":...,"started_at":...,"finished_at":...}`).

## Finding format

Write findings using `audit-core:audit-finding-writer`, with ID prefix `SEC`.
Use its canonical schema and severity rubric. Topic-specific field guidance:

- **Location:** `path/to/file.ext:LINE`
- **Evidence:**

```lang
<the exact line (redact the secret's tail), or the scan command + output>
```

- **Impact:** Plain language - what an attacker can do with the exposed value or the misconfiguration. One or two sentences with the severity justification.
- **Remediation:** The concrete fix in this stack: move to env/secret manager, ROTATE (it is already exposed), and purge from history where applicable.
- **Reference:** CWE-nnn, ASVS-x.y.z, OWASP-A0n:2021

Maps to `findings.json` fields `title`, `severity`, `confidence`, `location`,
`evidence`, `impact`, `remediation`, `references`, optional `tags`/`root_cause_key`.
Recurring references: CWE-798, CWE-321, CWE-489, CWE-942, CWE-16; ASVS 2.10,
14.1, 14.4/14.5; OWASP-A05:2021, A02:2021. Redact secret values in evidence.

## Output template (`audit/reports/audit-secrets-and-config.md`)

```markdown
# Secrets & Configuration audit

## Config key inventory
| Key | Source | Literal value? | Secret-like? | Flag | Location |
|---|---|---|---|---|---|
| ConnectionStrings:Default | file | Yes | Yes | YES | Api/appsettings.Production.json:9 |
| Jwt:Key | file | Yes | Yes | YES | Api/appsettings.Production.json:12 |
| ... | ... | ... | ... | ... | ... |

Source: file (literal in a committed file) | env | secret-mgr.

## Commits containing secrets to purge
| Commit | File | Secret type |
|---|---|---|
| 3f2a1c... | Api/appsettings.Production.json | JWT signing key |

## Findings
(generated by `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py md`.)

### Not checked
- <item> - <reason>
```

## Examples

**Input:** `appsettings.Production.json:12` -> `"Key": "hardcoded-...-0001"` under
`Jwt`.
**Finding:** `[Critical] SEC-001 - JWT signing key committed in production
appsettings` - Impact "anyone with repo read access can mint valid tokens for any
user/role"; Remediation "move to env/Key Vault via `Configuration["Jwt:Key"]`,
rotate now, purge from history with git filter-repo"; Reference CWE-798,
ASVS-2.10.4, OWASP-A02:2021.

**Input:** `Program.cs` -> `SetIsOriginAllowed(_ => true) ... .AllowCredentials()`.
**Finding:** `[High] SEC-004 - CORS reflects any origin and allows credentials` -
Impact "any website can make authenticated cross-origin calls with the victim's
cookies"; Remediation "replace with `WithOrigins("https://app.example.com")`;
never pair a wildcard/reflected origin with AllowCredentials"; Reference CWE-942,
OWASP-A05:2021.

## Bundled files

- `references/<stack>.md` - per-stack config keys, dangerous shapes, false positives (dotnet, java-spring, node-express, python-django, angular, react, vue; to add a stack, copy `$AUDIT_CORE_ROOT/skills/audit-stack-detection/references/stack-reference-template.md`).
- `references/tool-candidates.md` - secret-scanning tool candidates with invocations, plus rotation/purge steps.
- `scripts/git_secret_scan.py` - full git-history secret scan: secret value rules from `audit-sensitive-data-catalog` over `audit-git-history` added-lines; reports commit+file+line and `not_checked`. Default credentials (admin, sa) still count as committed literals.
- `scripts/config_key_inventory.py` - every config key with its source (file/env/secret manager), flags literal secrets; key names and placeholders judged by `audit-sensitive-data-catalog` (default credentials stay literals), files walked with `audit-code-scan`'s `repo_walk`.
- `scripts/patterns/<stack>.json` - the working-tree candidate pass, run with `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py`.
- Atomic scripts called: `$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py`,
  `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py`, `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py`;
  imported: `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/repo_walk.py`, `$AUDIT_CORE_ROOT/skills/audit-sensitive-data-catalog/scripts/catalog.py`,
  `$AUDIT_CORE_ROOT/skills/audit-git-history/scripts/githist.py`.
- `evals/` - a sample .NET repo planting a committed API key, a connection-string password, wildcard CORS with credentials, and a debug flag on in production, plus negatives.
