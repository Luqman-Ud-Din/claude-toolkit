# Consuming other skills' findings

Technical debt overlaps with almost every quality skill. Re-detecting their issues
would double-count them in the report and give two severities for one defect, so this
skill **reads `audit/findings/*.json` and maps findings into debt items by id prefix.
It never re-flags them.** Its own detectors cover only what no sibling owns.

## Contract

- Input: every `audit/findings/<skill>.json` except `audit-technical-debt.json`, in the
  schema of `$AUDIT_CORE_ROOT/skills/audit-finding-writer/references/findings-schema.md`.
- Findings with `confidence: false-positive` are ignored.
- Each mapped finding becomes one inventory row: `item` = "<ID>: <title>",
  `category` from the table, `impact` from severity, `effort` from an `effort:S|M|L|XL`
  tag or the default below, `finding_ref` = the original id, `source` = the skill.
- A consumed finding is never rewritten as a DEBT finding, even when it is a launch
  risk; the inventory marks it `launch_risk` and points at the original id.
- A native debt item at the same `file:line` as a consumed finding is dropped and the
  consumed row gets "also detected by <script>".
- An EOL item for a package that a DEP finding already names (title, tags, evidence or
  `root_cause_key`) links to that DEP id and produces no DEBT finding.
- A primary sibling that has not run is listed under "Not checked" ("no
  audit/findings/<skill>.json; its issues are not re-detected here"). Do not fill the gap
  by grepping for its issues yourself; run that skill, then re-run `debt_score.py`.

## Prefix map

| Prefix | Skill | Debt category | Default effort | What the debt view adds |
|---|---|---|---|---|
| TEST | audit-test-coverage-and-ci | test-debt | M | ranks untested hotspots; "tests" score input; hotspot launch-risk trigger |
| DEP | audit-dependency-vulnerabilities | dependency | S | "currency" score input; de-duplicates EOL packages; abandoned packages become debt rows |
| FEBP | audit-frontend-best-practices | frontend-practices | M | legacy/modern mixing, deprecated framework APIs and lint gaps enter the roadmap |
| ORM | audit-orm-query-and-data-access | data-access | M | churn multiplier on the repository/manager file |
| ASYNC | audit-async-and-dependency-injection | async-di | M | same |
| LEAK | audit-backend-resource-leak | resource-leak | M | same |
| FELEAK | audit-frontend-memory-leak | resource-leak | S | same |
| ARCH | audit-system-design | design | XL | design findings land in "long term" unless they carry a smaller effort tag |
| DB | audit-db-schema | schema | L | optional mapping |
| API | audit-api-contract | api-contract | M | optional mapping |
| PERF | audit-performance-and-scalability | performance | M | optional mapping |
| LOG | audit-logging-and-observability | observability | M | optional mapping |
| TIME | audit-datetime-and-timezone | datetime | M | optional mapping |
| A11Y | audit-accessibility-and-i18n | accessibility-i18n | M | optional mapping |
| INFRA | audit-infra-and-deployment | infrastructure | M | optional mapping |
| LIC | audit-licensing-and-compliance | licensing | M | optional mapping |

The first eight are the primary inputs; ORM, ASYNC, LEAK, FELEAK, FEBP and ARCH feed the
"quality findings" score input, TEST feeds "tests", DEP feeds "currency".

Not mapped (counted in "not treated as debt"): AUTHZ, INJ, SEC, HDR, XSS, CAUTH, TENANT,
RACE, BIZ, GDPR, SOC2, PII, READY, MAP, FW, RPT, APP. These are defects or compliance gaps
with their own owners and launch gates; calling them "debt" would soften them.

## Asking siblings for better input

- Tag findings with `effort:S|M|L|XL` when the fix size is known; the roadmap uses it.
- Set `root_cause_key` (for DEP: `<ecosystem>:<package>@<version>`) so EOL and dependency
  rows link reliably.
- `audit-test-coverage-and-ci` evidence `tests.json` (untested critical units, skipped
  tests) and `audit-dependency-vulnerabilities` evidence `dep-audit.json` (abandoned
  packages) can be quoted in the report's test-debt and dependency sections; they are not
  scored separately to avoid counting the same gap twice.
