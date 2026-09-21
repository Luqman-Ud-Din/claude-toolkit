---
name: audit-finding-writer
description: Turns raw audit observations (a grep hit, a scanner output line, a code snippet, or a one-sentence reviewer note) into complete, correctly-rated findings in the standard audit format - Title, Severity, Location, Evidence, Impact, Remediation, Reference - and appends them to findings.json. Use this whenever the user asks to write up, format, document, rate, or de-duplicate an audit finding, security issue, vulnerability, code-review defect, or "put this in the report", and whenever any other audit-* skill needs to emit findings. Trigger even when the user does not say "finding" but pastes evidence and asks what severity it is or how to describe it for a report.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-core:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit finding writer

Every audit skill in this family emits findings in one shared format so
`audit-report-generator` can assemble them and `audit-owasp-asvs-mapper` can map
them. This skill is the authority on that format. It takes messy input and
produces a finding a non-engineer can read and an engineer can act on.

Read-only rule: this skill never edits the audited code. It only writes under
`audit/` (findings, reports, evidence).

## Inputs you will receive

- A raw grep or scanner line: `src/Config.cs:12: var key = "sk_live_51H...";`
- A scanner JSON/CSV row (npm audit, dotnet list package --vulnerable, trivy, semgrep).
- A code snippet the reviewer pasted.
- A one-line note: "the /orders list endpoint has no paging".
- A batch of any of the above from another audit skill's automated pass (`hits.json` from `../audit-code-scan/scripts/grep_scan.py`).

Ask for the missing piece only when the finding cannot be rated without it (for
example, you cannot tell whether an endpoint is reachable unauthenticated). Otherwise
make the best call, state the assumption inside the Evidence or Impact text, and
set `confidence` to `likely`.

Prerequisites: Python 3 (stdlib only), and these sibling skills installed next to this one:
`audit-stack-detection` (stack resolution), `audit-findings-rollup` (de-duplication).

## Workflow

1. **Resolve the stack** so remediation is written in the project's idiom.
   Run `python ../audit-stack-detection/scripts/detect_stack.py <repo>` (it returns `audit/stack.json` when
   the orchestrator already wrote it). Open only the matching
   `references/<stack>.md`; it holds the remediation idioms and the reference ids
   that recur for that stack. If nothing matches, use
   `../audit-stack-detection/references/stack-reference-template.md` as the outline and say so in the finding.
2. **Locate and confirm.** Open the file at the reported line. Read enough
   surrounding code to answer: where does the data come from, who can reach this
   path, what does the code do with it. A finding whose Evidence is only the grep
   line is a candidate, not a finding; downgrade `confidence` to `likely` if you
   could not trace it.
3. **Rate severity** with `references/severity-rubric.md` (exploitability ×
   impact, CVSS-style). Write the one-line justification into the Impact field
   so reviewers can disagree with the rating on the merits.
4. **Write the finding** using the block below. Impact is written for a product
   owner: what can happen to customers, data, money, or uptime, not which CWE it
   is. Remediation is written for the engineer who owns the file: the concrete
   change, with a short code example in the project's stack.
5. **De-duplicate.** If two observations share one root cause (the same missing
   filter in a base repository, the same config key in three environments),
   emit one finding with multiple locations listed in Evidence and set
   `root_cause_key`. Preview the merge of entries that already share a key with
   `python ../audit-findings-rollup/scripts/findings_rollup.py dedupe audit/findings/<skill>.json`,
   then apply it with `--write` (add `--key title` to merge identical titles instead).
   False positives never merge.
6. **Emit.** Append to `audit/findings/<skill>.json` with
   `python scripts/findings.py add <file> --from <finding.json>` (validates the
   shape), then regenerate the Markdown section with
   `python scripts/findings.py md <file> --out audit/reports/<skill>.md`.
   When called by another skill, use that skill's name and id prefix
   (table in `references/findings-schema.md`), not `FW`.
7. **Say what was not checked.** If you rated without tracing, or could not open
   a file, add it to `scope.not_checked` with the reason. An honest gap is worth
   more than a confident guess.

## Finding block (fixed field order)

```markdown
### [Severity] PREFIX-NNN - Title in one clause, names the defect not the fix
- **Location:** `path/to/file.ext:LINE` (symbol)
- **Confidence:** confirmed | likely
- **Evidence:**

```lang
<the exact lines, or the command and its output>
```

- **Impact:** Plain language. Who is affected, what they lose, how likely. One or two sentences.
- **Remediation:** The concrete fix in this stack, with a short example. Name the file and the pattern to use.
- **Reference:** CWE-nnn, ASVS-x.y.z, OWASP-A0n:2021 (use what applies; see references/<stack>.md)
```

The same content goes into `findings.json` fields `title`, `severity`,
`confidence`, `location`, `evidence`, `impact`, `remediation`, `references`.
Full schema and the per-skill id prefixes: `references/findings-schema.md`.

## Tone and wording

- Factual and non-blaming: describe the code, not the author. "The handler trusts
  the tenantId from the body" rather than "the developer forgot".
- No jargon in Impact. "Someone could download another customer's invoices" beats
  "IDOR on the invoice resource".
- Title names the defect: "JWT signing key committed in appsettings.json", not
  "Fix secrets".
- One finding per root cause; one root cause per finding.
- Do not inflate severity to get attention; the rubric decides. An Info finding
  that is well-argued is more useful than a Medium that is not.

## Examples

**Input (raw grep line):**
`InventoryBackend/Account.MicroAPI/appsettings.Production.json:14:    "JwtKey": "Xk9...=="`

**Output:**
```markdown
### [Critical] SEC-001 - JWT signing key committed in production appsettings
- **Location:** `InventoryBackend/Account.MicroAPI/appsettings.Production.json:14`
- **Confidence:** confirmed
- **Evidence:**

```json
"JwtKey": "Xk9...=="   // present in git history since commit 3f2a1c
```

- **Impact:** Anyone with read access to the repository can mint valid tokens for any user and any role, including SuperAdmin, without knowing a password.
- **Remediation:** Move the key to the host's secret store (environment variable or Key Vault) and read it via `builder.Configuration["Jwt:Key"]`; rotate the key now since it is already exposed; purge it from history with `git filter-repo` and force-push after coordinating with the team.
- **Reference:** CWE-798, ASVS-2.10.4, OWASP-A02:2021
```

**Input (reviewer note):**
"the GET /api/orders list has no paging"

**Output:**
```markdown
### [Medium] API-004 - Order list endpoint returns the entire table
- **Location:** `src/orders/orders.controller.ts:22` (listOrders)
- **Confidence:** likely
- **Evidence:**

```ts
@Get() listOrders() { return this.repo.find(); }   // no take/skip, no filter
```

- **Impact:** As order volume grows every call gets slower and heavier; a single client refreshing a list can tie up the database and degrade the service for everyone. Rated Medium (easy to trigger, availability impact only) rather than High because it requires an authenticated user.
- **Remediation:** Accept `page`/`pageSize` query parameters, cap `pageSize` at 100, and pass them as `take`/`skip`; return `totalCount` so the client can paginate.
- **Reference:** CWE-770, ASVS-12.1.1
```

## Bundled files

- `references/severity-rubric.md` - how to pick Critical..Info, with examples.
- `references/findings-schema.md` - JSON schema, Markdown block, id prefixes, file paths.
- `references/<stack>.md` - remediation idioms and recurring references per stack
  (dotnet, java-spring, node-express, python-django, angular, react, vue); add a stack from
  `../audit-stack-detection/references/stack-reference-template.md`.
- `scripts/findings.py` - init / add / validate / md / summary for findings.json. Owned here;
  every other audit skill calls `../audit-finding-writer/scripts/findings.py`.
- Atomic scripts called: `../audit-stack-detection/scripts/detect_stack.py` (stack detection,
  honours `audit/stack.json`) and `../audit-findings-rollup/scripts/findings_rollup.py dedupe`
  (merge findings that share `root_cause_key`).
- `evals/` - sample raw inputs and the expected findings, for testing the skill.
