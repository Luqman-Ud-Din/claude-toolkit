# Scoring and prioritisation

How `scripts/debt_score.py` turns evidence into a ranked inventory, a roadmap and one
maintainability score. The numbers are defaults chosen to be explainable, not
precise; change them in the script (constants at the top) when a team disagrees, and
say so in the report.

## 1. Why churn matters

Debt costs interest only when someone has to change the code. A 400-line function that
nobody touched in two years is ugly but cheap; the same function edited in eight of the
last ten commits taxes every one of those changes and is where regressions come from.
This is the "hotspot" idea (Adam Tornhill, *Your Code as a Crime Scene*): rank by
change frequency x complexity, then read the top few by hand.

- **Function hotspot score** = commits touching the function in the window x its cyclomatic complexity.
- **File hotspot score** = commits touching the file x its highest function CC (used only
  when function-level churn is unavailable for that file).
- Window: last 365 days by default; use `--last-commits N` for young or very active repos,
  and start the window after any bulk reformat commit (or list it in `.git-blame-ignore-revs`).

## 2. Impact (1-10)

| Category | Rule |
|---|---|
| hotspot (top-10 churn x complexity, >= 2 commits, CC over threshold) | 6 + min(3, CC / 25) + 1 if > 150 lines |
| complexity (not hot) | 6 if CC > 50, 4 if > 20, else 2; +1 if > 150 lines |
| oversized-file | 3 (> 1000 lines), 5 (> 2000) |
| duplication | 2 + min(3, lines / 10) + 1 for near-identical functions + 1 if in a hotspot function - 1 if test-only |
| dead-code | module 3, symbol 1, unreachable 2, orphan project 2 |
| todo | TODO 1, FIXME 2, HACK/XXX 3; +1 if > 1 year, +1 more if > 3 years; +2 if it mentions auth, tokens, tenants, payments, crypto |
| commented-out-code | 1, or 2 when >= 10 lines |
| suppression (grouped by tool + rule) | security rule 6, blanket or project-wide 3, specific 1; +1 at >= 10 places |
| eol-runtime / eol-framework / eol-package | past EOL 8, +1 for runtimes and security-sensitive packages; floor-only (`>=16`) 4; EOL within 180 days 5, within 90 days 6 |
| deprecated-api (grouped by pattern) | pattern hint Info 1, Low 2, Medium 4, High 6; +1 at >= 10 uses |
| inconsistent-pattern (family with >= 2 variants) | 3, or 4 with >= 3 variants |
| docs | README missing 4, runbook missing 3, README partial / stale 2, dangling doc paths 2, API docs missing 2, no ADRs 1 |
| consumed finding | Critical 10, High 8, Medium 5, Low 3, Info 1 (from the finding's severity) |

## 3. Effort (S / M / L / XL)

| Size | Meaning | Points |
|---|---|---|
| S | under a day, one person, no coordination | 1.0 |
| M | up to a week; needs tests or a small design note | 1.5 |
| L | a sprint-sized piece; touches several modules or needs a migration | 2.0 |
| XL | multi-sprint or cross-team; needs a plan, budget and staged rollout | 3.0 |

Defaults: hotspot/complexity L when > 150 lines or CC > 50, XL when > 600 lines or CC > 150,
else M; duplicates S for a two-place clone of <= 30 lines, else M; dead code, TODOs,
commented-out code and suppressions S (HACK/XXX and security suppressions M); EOL runtime,
framework or security-sensitive package L, other packages M; deprecated API S (<= 5 uses),
M (< 30), L; inconsistent pattern M (<= 20 uses) or L. Consumed findings take `effort:X`
from their tags when present, else the per-prefix default in `consumed-findings.md`.
Override the effort by hand when you know better (a shared helper makes a big clone S) and
note why.

## 4. Priority and buckets

```
multiplier = 1 + commits touching the item's function (or file) / most commits any file received
             (1.0 for repo-wide items and when there is no history)
priority   = impact x multiplier / effort points
```

Buckets (the roadmap):
- **Quick wins**: effort S, or effort M with impact >= 6.
- **Long term**: effort XL, or effort L with impact <= 4.
- **Next quarter**: everything else.

Launch-risk items keep their bucket but are marked; their DEBT finding is what the launch
decision uses. For a hotspot, the roadmap note names the first slice that fits a quick win
(characterization tests around the function) so the big item starts immediately.

Worked example (the eval fixture, 10-commit window, max file commits 8):

| Item | Impact | Multiplier | Effort | Priority |
|---|---|---|---|---|
| `ImportOrders` CC 118, 405 lines, 8 of 10 commits | 10 | 2.0 | L (2.0) | 10.0 |
| `DEP-001` Newtonsoft.Json (consumed, High) | 8 | 1.125 | S (1.0) | 9.0 |
| WebClient obsolete API inside the hot file | 4 | 2.0 | S | 8.0 |
| near-identical `CalculateInvoiceTotal` / `CalculateQuoteTotal` | 5 | 1.125 | S | 5.62 |
| `TEST-001` no test project (consumed, High) | 8 | 1.0 | M (1.5) | 5.33 |
| IdentityServer4 past EOL | 9 | 1.125 | L | 5.06 |
| 3-year-old TODO in `Program.cs` | 3 | 1.25 | S | 3.75 |
| unused `LegacyCsvExporter` module | 3 | 1.0 | S | 3.0 |

## 5. Maintainability score (0-100)

Weighted mean of the sub-scores whose inputs exist. A missing input is excluded and its
weight redistributed; the report lists it so a high score cannot hide an unmeasured area.

| Input | Weight | Sub-score |
|---|---|---|
| complexity | 20 | 100 - 150 x (share of function lines inside functions with CC > threshold) |
| hotspots | 15 | 100 x (1 - share of code-file changes that landed in files holding a CC > threshold function) |
| duplication | 10 | 100 - 5 x duplication % |
| dead code | 5 | 100 - (20 x modules + 4 x symbols + 10 x unreachable + 10 x orphan projects) / KLOC (min 1) |
| currency | 15 | 100 - 35 per past-EOL item - 10 per EOL-soon - 5 per EOL floor - 10 per High/Critical DEP finding - 4 per Medium - 1 per Low |
| hygiene | 10 | 100 - 5 x weighted markers per KLOC: TODO 1 / FIXME 2 / HACK 3 x (1 + age years / 2, age capped at 5), commented-out block 2, suppression 1 (blanket 3, security 5), deprecated use 1, mixed family 5 |
| tests | 10 | 100 - 35 per High/Critical TEST finding - 15 per Medium - 5 per Low |
| docs | 5 | README present 30 (partial 15) + fresh 20 (unknown age 10) + API docs 15 + ADRs 15 + runbook 20 |
| quality findings | 10 | 100 - 25 per Critical, 12 per High, 5 per Medium, 2 per Low from ORM/ASYNC/LEAK/FELEAK/FEBP/ARCH |

Sub-scores are clamped to 0-100. Grades: A >= 85, B >= 70, C >= 55, D >= 40, E < 40.
Report the table with every input's measured value, not just the number: the score is a
trend indicator for the same repo over time, not a comparison between repos.

## 6. Launch risks (the only items that become findings)

| Trigger | Severity | Reference |
|---|---|---|
| Runtime, backend framework or security-sensitive package past EOL, not already a DEP finding | High | CWE-1104, ASVS-14.2.1, OWASP-A06:2021 |
| Frontend framework or other package past EOL, not already a DEP finding | Medium | CWE-1104, OWASP-A06:2021 |
| Runtime/framework EOL within 90 days | Low | CWE-1104 |
| Top-3 hotspot with CC >= 50 and no tests covering it (TEST findings, or no test files) | Medium | CWE-1121, CWE-1120 |
| Security analyzer rule suppressed (CA2100, CA5xxx, SCS, Sonar S2068/S5332, eslint security/*, nosec) | Medium | CWE-1127 |
| FIXME/HACK (or TODO older than a year) that mentions auth, tokens, tenants, payments or crypto | Low | CWE-546 |

Raise or lower with the severity rubric in
`$AUDIT_CORE_ROOT/skills/audit-finding-writer/references/severity-rubric.md` after reading the code: an EOL
package used only by a build script is not High. Everything else stays in the inventory.
