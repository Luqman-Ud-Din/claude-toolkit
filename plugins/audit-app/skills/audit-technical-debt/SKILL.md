---
name: audit-technical-debt
description: Quantifies and prioritises technical debt for post-launch pay-down - dead and unreachable code, duplicated blocks, cyclomatic/cognitive complexity hotspots, oversized files and functions, TODO/FIXME/HACK comments aged with git blame, outdated dependencies and end-of-life runtimes and frameworks, deprecated APIs, missing or stale docs (README, ADRs, API docs, runbooks), inconsistent patterns, commented-out code, lint/analyzer suppressions and test debt. Ranks impact against effort, finds churn x complexity hotspots from git history, reuses other audit skills' findings instead of re-detecting them, and outputs a debt inventory, hotspot list, quick-win/next-quarter/long-term roadmap and maintainability score. Use it whenever the user asks about technical debt, code health, maintainability, refactoring priorities, code smells, legacy code, dead or duplicate code, complexity, hotspots, churn, TODOs, outdated or EOL dependencies, deprecated APIs, or "what should we clean up", even when they do not name this skill.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-app:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit: technical debt

Turns "the code is messy" into a ranked list a team can plan against: what the debt
is, where it is, how old it is, how much it slows change or raises risk, how much it
costs to fix, and in which order to pay it down. Most debt is not a launch blocker;
the few items that are become standard findings, and everything else goes into the
inventory and roadmap.

The central idea is that debt only charges interest where code changes. A complex
function nobody touches can wait; a complex function edited in most recent commits is
where regressions come from. Rank by churn x complexity first, then read the top
items by hand.

Read-only rule: never modify the audited code, manifests or git state (no installs,
no `--fix`, no codemods in the repo). Git is read only through `audit-git-history`, which
runs read-only commands (`log`, `blame`, `rev-parse`). Write only under `audit/`.

## Inputs and prerequisites

- Skills from the `audit-core` plugin (reached via `$AUDIT_CORE_ROOT`, exported by that plugin; a sibling `skills/` layout also works): `audit-stack-detection`,
  `audit-code-scan`, `audit-finding-writer`, `audit-git-history` and `audit-findings-rollup`.
  The scripts exit with a message naming the missing one.
- Repo root. Standalone runs read `audit/stack.json` if present, else run
  `python "$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py" <repo>`.
- Git history, for churn and ages. Three modes (details in `references/git-history.md`):
  a normal work tree (default); `--history <file>` with a synthetic history JSON when the
  repo has no `.git` (exports, fixtures); `--no-git` for a complexity-only run that says so.
  Check for shallow clones and bulk-reformat commits before trusting churn.
- Other skills' findings in `audit/findings/*.json`. The primary inputs are
  `audit-test-coverage-and-ci` (TEST), `audit-dependency-vulnerabilities` (DEP),
  `audit-frontend-best-practices` (FEBP), `audit-orm-query-and-data-access` (ORM),
  `audit-async-and-dependency-injection` (ASYNC), `audit-backend-resource-leak` (LEAK),
  `audit-frontend-memory-leak` (FELEAK) and `audit-system-design` (ARCH). Run them first
  when possible; a missing one is reported as not checked, not re-done here.
- Python 3 stdlib only. Stack tools (Roslyn metrics, PMD, ESLint, radon, knip, vulture,
  jscpd) are optional confirmations listed in each stack reference; run them in a scratch
  copy if they need installing.

## Consume, do not re-detect

This skill maps other skills' findings into debt items **by id prefix** and never
re-flags them (full contract: `references/consumed-findings.md`):

| Prefix | Becomes debt category | Why it is not re-detected here |
|---|---|---|
| TEST | test-debt | coverage map and skipped tests belong to audit-test-coverage-and-ci |
| DEP | dependency | vulnerable and abandoned packages belong to audit-dependency-vulnerabilities |
| FEBP | frontend-practices | legacy/modern mixing, deprecated framework APIs, lint config |
| ORM / ASYNC / LEAK / FELEAK | data-access / async-di / resource-leak | defect patterns with their own severity |
| ARCH | design | coupling, cycles, ownership |

A native item at the same file:line as a consumed finding is dropped; an EOL package
that a DEP finding already names links to it. Security and compliance prefixes (AUTHZ,
INJ, SEC, XSS, TENANT, ...) are not debt and are only counted.

## Workflow

1. **Resolve the stack.** `python "$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py" <repo>`; open only
   `references/<stack>.md` for each detected backend and frontend (dotnet, java-spring,
   node-express, python-django, angular, react, vue). Unknown stack: follow
   `$AUDIT_CORE_ROOT/skills/audit-stack-detection/references/stack-reference-template.md`, run the
   language-agnostic scripts anyway, and record the gap. Read `references/scoring-and-prioritisation.md` once.

2. **Automated pass.** Write everything to `audit/evidence/audit-technical-debt/`
   (`E` below). Add `--history <file>` or `--no-git` to the history-aware scripts when
   needed, and `--as-of YYYY-MM-DD` for a reproducible run.
   - `python scripts/complexity.py <repo> --out E/complexity.json --md E/complexity.md` -
     per-function cyclomatic (branch-keyword count) and approximate cognitive complexity,
     function and file length for C#, Java, TS/JS, Python and Vue/Angular component scripts.
   - `python scripts/churn.py <repo> --complexity E/complexity.json [--since-days 365 | --last-commits N] --out E/churn.json --md E/churn.md` -
     `git log --numstat` per file, per-function commits where cheap (hunk mapping for the
     top files), joined with complexity into the hotspot ranking.
   - `python scripts/todo_age.py <repo> --out E/todos.json --md E/todos.md` - TODO/FIXME/HACK/XXX
     with blame author, date and age, plus commented-out code blocks.
   - `python scripts/duplicates.py <repo> --min-lines 6 --out E/duplicates.json --md E/duplicates.md` -
     normalised-line rolling-hash clones; flags near-identical functions.
   - `python scripts/dead_code.py <repo> --out E/dead_code.json --md E/dead_code.md` -
     unreferenced modules, files and exported symbols, unreachable statements, projects
     missing from the solution. **Heuristic: reflection, DI scanning, templates and other
     repos are invisible to it; every row is a candidate.**
   - `python scripts/eol_check.py <repo> --out E/eol.json --md E/eol.md` - target
     frameworks, engines, python_requires, Java version, framework majors and known EOL
     packages against `references/eol-dates.json`. The table has an `as_of` date (currently
     2026-05-31) and needs refreshing at least quarterly; the output flags a stale table.
   - `python scripts/suppressions.py <repo> --out E/suppressions.json --md E/suppressions.md` -
     `#pragma warning disable`, `SuppressMessage`, `NoWarn`, `eslint-disable`, `@ts-ignore`,
     `noqa`, `nosec`, `@SuppressWarnings`, with blanket, justification and security flags.
   - `python scripts/docs_check.py <repo> --out E/docs.json --md E/docs.md` - README,
     freshness against code changes, ADRs, API docs, runbooks, dangling doc paths.
   - `python "$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py" <repo> --patterns scripts/patterns/<stack>.json --out E/hits.json` -
     deprecated APIs (`DEPR-*`) and mixed approaches (`MIX-<family>-<variant>`; a family
     with two or more variants in use is an inconsistent pattern).
   - `python scripts/debt_score.py <repo> --evidence E --findings-dir audit/findings --out E/debt.json --md E/debt.md --candidates-dir E/candidates` -
     reads all of the above plus the sibling findings, builds the inventory, roadmap,
     maintainability score and draft DEBT findings for launch risks.

3. **Manual trace of the highest-value items**, in this order:
   1. **Top three hotspots.** Open each function. List the business rules its branches
      encode, which tests pin them (TEST findings), and the seams where it can be split.
      Confirm the churn is real (not a formatting sweep). Write the first slice that fits
      a quick win (usually characterization tests) into the roadmap note.
   2. **Past-EOL runtimes, frameworks and packages.** Confirm the version actually deployed
      (Dockerfile, CI, lockfile), where the component sits (auth path? build-only?), and the
      migration path and cost. That decides severity and effort.
   3. **Security-related suppressions and security TODOs.** Read the suppressed code.
   4. **Dead-code candidates.** Search the solution and sibling repos for string and
      reflection uses before calling anything dead; downgrade or drop what you cannot confirm.
   5. **Duplicates and mixed patterns.** For near-identical functions, diff them: have they
      already diverged (a bug fixed in one)? For mixed families, find whether a migration
      is under way (an ADR, newest code in one style).
   6. **Docs.** Skim the README and newest ADR against the code; flag statements that are wrong,
      not only files that are missing.
   Adjust impact or effort in `debt.json` when the trace shows the default was wrong, and
   say why in the item's notes.

4. **Write findings only for launch risks.** Take the drafts in `E/candidates/`, confirm
   each against the code, set `confidence: confirmed` or drop it, then
   `python "$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py" init audit-technical-debt` (once) and
   `python "$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py" add audit/findings/audit-technical-debt.json --from E/candidates/DEBT-00N.json`,
   then `validate`. Default triggers and severities (rubric:
   `$AUDIT_CORE_ROOT/skills/audit-finding-writer/references/severity-rubric.md`): runtime, backend framework or
   security-sensitive package past EOL and not already a DEP finding = High; other past-EOL
   component = Medium; EOL within 90 days = Low; top-three hotspot with CC >= 50 and no
   tests = Medium; suppressed security analyzer rule = Medium; security FIXME/HACK = Low.
   Never write DEBT findings for consumed items or for ordinary debt.

5. **Produce the outputs** (paths relative to the audited repo):
   - `audit/findings/audit-technical-debt.json` - launch-risk findings only.
   - `audit/reports/audit-technical-debt.md` - the template below, built from `E/debt.md`
     plus your trace notes.
   - `audit/evidence/audit-technical-debt/` - every script output, candidates, trace notes.
   - `audit/status/audit-technical-debt.json` -
     the status record defined in `audit-core:audit-finding-writer` (references/run-status.md).

6. **List what was not checked** and why: copy `debt.json.not_checked` (missing sibling
   skills, missing evidence, history mode none or shallow, stale EOL table) and add what the
   heuristics cannot see (reflection and DI-scanned code, templates, other repositories,
   runtime-only deprecation warnings, documentation correctness beyond the sample you read,
   code generated at build time). Also state which files the numbers exclude: the scripts
   walk the repo with `audit-code-scan`'s `repo_walk` (its standard skip list: `node_modules`,
   `bin`, `obj`, `dist`, `build`, `target`, `coverage`, `audit` and tool caches), plus
   `vendor/` everywhere, `Migrations/` and hidden folders for complexity, duplicates and dead
   code, and files over 2 MB (except the docs listing). `packages/` folders are read; add
   `--exclude "packages/*"` to complexity, duplicates and dead code for a legacy NuGet
   `packages/` folder.

## Finding format

Write findings using `audit-core:audit-finding-writer`, with ID prefix `DEBT`.
Use its canonical schema and severity rubric. Topic-specific field guidance:

- **Location:** `path/to/file.ext:LINE` (symbol or package)
- **Evidence:**

```text
<manifest line, script output row (complexity/churn/eol), or the suppressed code>
```

- **Impact:** Plain language: what breaks or stays unpatched, for whom, and why it matters before launch.
- **Remediation:** The concrete change and its first step, sized; the migration path for EOL items.
- **Reference:** CWE-1104 / ASVS-14.2.1 / OWASP-A06:2021 (EOL), CWE-1121 + CWE-1120 (untested hotspot), CWE-1127 (suppression), CWE-546 (comment)


The same content goes into `findings.json` (`title`, `severity`, `confidence`, `location`,
`evidence`, `impact`, `remediation`, `references`), with `tags: ["technical-debt", <category>]`
and `root_cause_key` such as `eol:IdentityServer4@*` or `hotspot:<file>:<function>`.

## Output template (`audit/reports/audit-technical-debt.md`)

```markdown
## audit-technical-debt

**Target:** <repo> @ <commit> - **As of:** <date> - **History:** git | synthetic | none (<reason>)
**Maintainability score:** <n>/100 (grade <A-E>) - **Debt items:** <n> - **Launch-risk findings:** Critical n / High n / Medium n / Low n

### Maintainability score
| Input | Measure | Sub-score | Weight | Contribution |
|---|---|---|---|---|
| complexity | 77% of function lines in functions with CC > 15 | 0 | 20 | 0.0 |
| ... | | | | |
Missing inputs are excluded and their weight redistributed; they are listed under Not checked.

### Debt inventory
| Rank | ID | Item | Category | Location | Age (days) | Impact (1-10) | Effort (S/M/L/XL) | Priority | Bucket | Source / finding |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | TD-001 | ImportOrders: CC 118, 405 lines, 8 of last 10 commits | hotspot | `OrderService.Api/Services/OrderImportService.cs:22` | 9 | 10 | L | 10.0 | next-quarter | DEBT-002 |

### Churn vs complexity hotspots
| Rank | Function / file | Location | Commits in window | CC | Lines | Score | Tested? | First slice |
|---|---|---|---|---|---|---|---|---|

### Pay-down roadmap
**Quick wins (days, alongside feature work)** - TD-ids with one-line action each
**Next quarter (planned)** - TD-ids, owner area, expected outcome
**Long term (needs a plan and budget)** - TD-ids, prerequisite decisions (ADR, licence, migration)

### Consumed findings
| Prefix | Skill | Mapped to | Count | Not re-flagged |
|---|---|---|---|---|

### Findings (launch risks only)
(standard DEBT blocks, highest severity first)

### Not checked
- item - reason
```

## Examples

**Input:** `churn.py` row `#1 OrderService.Api/Services/OrderImportService.cs ImportOrders commits=8 cc=118 score=944`,
TEST-001 says the solution has no test project.

**Output:**
```markdown
### [Medium] DEBT-002 - ImportOrders is a 405-line, CC 118 function changed in 8 of the last 10 commits with no tests
- **Location:** `OrderService.Api/Services/OrderImportService.cs:22` (ImportOrders)
- **Confidence:** confirmed
- **Evidence:**

```text
complexity.py: OrderImportService.cs:22-426 cyclomatic=118 length=405
churn.py: hotspot #1, 8 of 10 commits in window (next: OrdersController.cs, 3 commits, CC 2)
TEST-001: no test project in OrderService.sln
```

- **Impact:** Almost every recent change to order import lands in one function that validates, prices, taxes, converts currency and allocates stock, and nothing checks it automatically; the next discount or tax tweak is likely to break another branch unnoticed until customers are charged wrongly. Medium: no known defect today, but the change rate makes a regression likely soon after launch.
- **Remediation:** Before more feature work, add characterization tests that pin ImportResult for representative rows (one per channel, tax country, FX path); then extract ValidateRow, PriceLines, ApplyTax, ConvertCurrency and AllocateStock one at a time behind those tests. Stop adding branches to ImportOrders.
- **Reference:** CWE-1121, CWE-1120
```

**Input:** `eol_check.py`: `IdentityServer4 (NuGet) 4.1.2 (2022-12-13) at OrderService.Api/OrderService.Api.csproj:10`,
no DEP finding names IdentityServer4.

**Output:** `[High] DEBT-001 - IdentityServer4 4.1.2 is past end-of-life and receives no security fixes`.
Remediation: migrate token issuance to Duende IdentityServer (licence needed) or OpenIddict. Until
then, record the accepted risk with an owner and date. The inventory row is next-quarter, effort L.
Newtonsoft.Json in the same file is not an EOL item: DEP-001 already covers it and appears only
as a consumed row.

## Bundled files

- `references/<stack>.md` - per-stack debt hotspots, deprecated APIs, EOL markers, suppression
  syntax, mixed-pattern families, false positives and tools (Roslyn metrics, PMD/CPD, jdeprscan,
  ESLint complexity, knip, ts-prune, radon/xenon, vulture, jscpd, SonarQube) for `dotnet`,
  `java-spring`, `node-express`, `python-django`, `angular`, `react`, `vue`. To add one, copy
  `$AUDIT_CORE_ROOT/skills/audit-stack-detection/references/stack-reference-template.md`.
- `references/scoring-and-prioritisation.md` - impact and effort rules, churn multiplier,
  priority, buckets, maintainability score weights, launch-risk triggers, worked example.
- `references/consumed-findings.md` - prefix map and the never-re-flag contract.
- `references/git-history.md` - git / synthetic / no-git modes and pitfalls; points to the
  audit-git-history contract for the synthetic format.
- `references/eol-dates.json` - EOL table with its `as_of` date; refresh quarterly.
- `scripts/complexity.py`, `churn.py`, `todo_age.py`, `duplicates.py`, `dead_code.py`,
  `eol_check.py`, `suppressions.py`, `docs_check.py`, `debt_score.py` - the automated pass.
- `scripts/patterns/<stack>.json` - deprecated APIs and mixed patterns, run by
  `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py`.
- Atomic scripts called from sibling skills: `$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py`
  (stack), `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py` (pattern pass) and `repo_walk.py` (file
  walker imported by every script), `$AUDIT_CORE_ROOT/skills/audit-git-history/scripts/githist.py` (history for
  churn, TODO ages and docs freshness), `$AUDIT_CORE_ROOT/skills/audit-findings-rollup/scripts/findings_rollup.py`
  (`debt_score.py` loads sibling findings with it), `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py`
  (init / add / validate DEBT findings).
- `evals/` - sample .NET repo (unused module, near-identical functions, a 405-line hot function
  changed in 8 of 10 commits, a 3-year-old TODO, an EOL package) plus
  `synthetic-git-history.json`, because the fixture cannot ship a `.git` folder.
