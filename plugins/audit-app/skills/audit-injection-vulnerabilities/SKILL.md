---
name: audit-injection-vulnerabilities
description: Finds injection vectors in backend code - SQL/NoSQL injection through raw queries and string-built commands, OS command injection, path traversal in file access, LDAP/XPath/template injection, SSRF through user-supplied URLs, and unsafe deserialization - by running a per-stack grep pass for dangerous APIs and then tracing every hit back to its input source to label it confirmed, likely, or false-positive. Use this whenever the user mentions injection, SQL injection, SQLi, NoSQL injection, SSRF, path traversal, directory traversal, command injection, shell injection, deserialization, raw queries, FromSqlRaw, string-concatenated SQL, "is this query safe", a backend security scan, an OWASP Top 10 check, or a pre-production security review - even when they do not name this skill and even when the request is a general "audit the backend for security".
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-app:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit: injection vulnerabilities

Injection is the class of bug where data the caller controls ends up being
interpreted as code or as a structural part of a command: SQL, NoSQL filters,
shell commands, file paths, LDAP or XPath queries, server-side templates,
outbound HTTP requests (SSRF), and serialized object graphs. This skill finds
the sinks with a stack-specific grep, then traces each sink back to its source
so the report says which hits are real, which are probable, and which are noise.

Read-only rule: never edit the audited code. Write only under `audit/`
(`findings`, `reports`, `evidence`, `status`).

## Inputs and prerequisites

- Path to the repository root (may contain several services; each is scanned).
- `audit/stack.json` if `audit-application` already ran; otherwise run
  `$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py`.
- Python 3 (stdlib only) for the bundled scripts.
- Skills from the `audit-core` plugin (reached via `$AUDIT_CORE_ROOT`, exported by that plugin; a sibling `skills/` layout also works): `audit-stack-detection` (stack), `audit-code-scan` (grep pass), `audit-finding-writer` (findings.json).
- Optional: the endpoint inventory from `audit-endpoint-inventory`
  (`audit/evidence/audit-endpoint-inventory/endpoints.json`, fields `auth.required` and
  `auth.anonymous_marker`) to know which sinks are reachable without authentication -
  this changes severity.

## Workflow

1. **Resolve the stack.** `python "$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py" <repo>` (returns the
   cached `audit/stack.json` when present). Open only the matching
   `references/<stack>.md` for each backend stack found; for a frontend-only
   repo open the matching frontend file, which explains what this skill covers
   on the client and hands the rest to `audit-frontend-xss-and-dom-safety`.
   No match: use `$AUDIT_CORE_ROOT/skills/audit-stack-detection/references/stack-reference-template.md` as the outline and say so in scope.
2. **Automated pass.** For every backend stack:
   `python "$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py" <repo> --patterns scripts/patterns/<stack>.json --out audit/evidence/audit-injection-vulnerabilities/hits-<stack>.json --md audit/evidence/audit-injection-vulnerabilities/hits-<stack>.md`.
   Every hit is a candidate. The pattern ids map to the classes in
   `references/injection-classes.md` (SQL, NOSQL, CMD, PATH, LDAP, XPATH, TMPL,
   SSRF, DESER). Also run the stack's own tooling from the reference's
   "Tooling" section when it is installed (Roslyn analyzers, semgrep, bandit,
   eslint-plugin-security) and save the raw output under `audit/evidence/`.
3. **Manual trace of the highest-risk flows.** For each hit, open the file and
   answer three questions: (a) where does the value come from - route/query/body
   parameter, header, uploaded file, database row previously written by a user,
   or a constant; (b) what transforms it before the sink - parameterization,
   allow-list, `Path.GetFileName`, URL host check, type cast; (c) who can reach
   it - anonymous, any authenticated user, admin, or a background job. Then
   label: `confirmed` (user-controlled source reaches the sink with no
   structural escaping), `likely` (source is user-controlled but the trace
   crosses a boundary you could not open - a stored procedure, a library, a
   queue message), `false-positive` (constant input, real parameterization, or a
   verified allow-list). Keep false positives in `findings.json` so the reviewer
   can see what was rejected and why. Beyond the hits, trace the flows the
   reference's "Manual trace checklist" names even if the grep was silent:
   search/filter/sort endpoints (dynamic ORDER BY), report/export builders,
   file download/upload handlers, webhook or "fetch this URL" features, and
   any `BinaryFormatter`/`ObjectInputStream`/`pickle`/`yaml.load` reader.
4. **Write findings** with `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py` in the standard format (block
   below), id prefix `INJ`. One finding per root cause: a helper that builds
   SQL for twelve callers is one finding with twelve locations in Evidence and
   a `root_cause_key`. Severity follows
   `audit-finding-writer/references/severity-rubric.md`: SQL injection on an
   anonymous route is Critical; the same behind auth in a multi-tenant app is
   High-to-Critical; path traversal limited to reading a public folder is Medium.
5. **Produce the outputs** (all paths relative to the audited repo):
   - `audit/findings/audit-injection-vulnerabilities.json` (via `findings.py init/add`)
   - `audit/reports/audit-injection-vulnerabilities.md` (skeleton below; run
     `findings.py md` for the findings section, then add the hit-triage table)
   - `audit/evidence/audit-injection-vulnerabilities/hits-<stack>.json|md` and any tool output
   - `audit/status/audit-injection-vulnerabilities.json`:
     the status record defined in `audit-core:audit-finding-writer` (references/run-status.md)
6. **List what was not checked** in `scope.not_checked` with the reason:
   stored procedures whose bodies are not in the repo, dynamic SQL inside
   database views, generated code, vendored libraries, services that failed to
   parse, and any class (for example LDAP) that does not apply to this app.
   Also list the automated pass's coverage limits from `audit-code-scan`: folders on the shared skip list (`node_modules`, `bin`, `obj`, `dist`, `build`, `.git`, `audit`, ... - see `$AUDIT_CORE_ROOT/skills/audit-code-scan/references/repo-walk-api.md`) and files over 2 MB are not read, and patterns match one line at a time.

## Finding format

Write findings using `audit-core:audit-finding-writer`, with ID prefix `INJ`.
Use its canonical schema and severity rubric. Topic-specific field guidance:

- **Confidence:** confirmed | likely | false-positive

- **Impact:** Plain language. Who is affected, what they lose, how likely. One or two sentences, ending with the severity justification.
- **Reference:** CWE-nnn, ASVS-x.y.z, OWASP-A0n:2021


Same content goes into the JSON fields `id`, `title`, `severity`, `confidence`,
`location`, `evidence`, `impact`, `remediation`, `references`, `tags`
(use the class id: `sql`, `nosql`, `cmd`, `path`, `ldap`, `xpath`, `template`,
`ssrf`, `deser`). Full schema and prefix table:
`audit-finding-writer/references/findings-schema.md`.

## Output template - `audit/reports/audit-injection-vulnerabilities.md`

```markdown
## audit-injection-vulnerabilities findings

| Critical | High | Medium | Low | Info |
|---|---|---|---|---|
| n | n | n | n | n |

### Scope
- Stack(s): dotnet (Account.MicroAPI, Product.MicroAPI), angular (frontend - URL/query building only)
- Pattern files: scripts/patterns/dotnet.json (NN patterns)
- Hits: NN total -> NN confirmed, NN likely, NN false-positive

### Hit triage
| Hit | Class | Location | Source of input | Label | Finding |
|---|---|---|---|---|---|
| SQL-RAW-CONCAT | sql | `Repo/ReportRepository.cs:41` | `sortBy` query param | confirmed | INJ-001 |
| SQL-RAW-CONCAT | sql | `Repo/ProductRepository.cs:88` | constant | false-positive | - |

### Findings
<one block per finding, Critical first>

### Not checked
- <item> - <reason>
```

## Examples

**Input (hit):** `Product.Managers/ReportManager.cs:41: var sql = "SELECT * FROM Sales WHERE BranchId = " + branchId + " ORDER BY " + sortBy;`

**Output:**
```markdown
### [High] INJ-001 - Sales report builds ORDER BY from the sortBy query parameter
- **Location:** `Product.Managers/ReportManager.cs:41` (GetSalesReport)
- **Confidence:** confirmed
- **Evidence:**

```csharp
var sql = "SELECT * FROM Sales WHERE BranchId = " + branchId + " ORDER BY " + sortBy;
return _context.Sales.FromSqlRaw(sql).ToList();   // sortBy = model.SortColumn, from the request body
```

- **Impact:** Any logged-in user can append SQL to the sort column and read or alter every tenant's sales rows in the shared database. Rated High rather than Critical because the route requires an authenticated account; move to Critical if self-registration is open.
- **Remediation:** Map `sortBy` through an allow-list (`new[]{"Date","Total"}.Contains(sortBy) ? sortBy : "Date"`) and pass `branchId` as a parameter: `FromSqlInterpolated($"SELECT * FROM Sales WHERE BranchId = {branchId}")` then `.OrderBy(...)` in LINQ.
- **Reference:** CWE-89, ASVS-5.3.4, OWASP-A03:2021
```

**Input (hit):** `Repositories/ProductRepository.cs:88: _context.Products.FromSqlRaw("SELECT * FROM Products WHERE Sku = {0}", sku)`

**Output:** label `false-positive` in the triage table with the note "`{0}` placeholder
with a parameter argument - EF Core sends it as `@p0`"; no finding block is
emitted, but the entry stays in `findings.json` with `confidence: false-positive`.

## Bundled files

- `references/injection-classes.md` - the nine classes, source/sink vocabulary, the confidence rubric, and severity anchors.
- `references/<stack>.md` - dangerous APIs, safe idioms, manual trace checklist, false positives, tooling per stack (`dotnet`, `java-spring`, `node-express`, `python-django`; `angular`, `react`, `vue` cover the client half). To add a stack, follow `$AUDIT_CORE_ROOT/skills/audit-stack-detection/references/stack-reference-template.md`.
- `scripts/patterns/<stack>.json` - the dangerous-API pattern lists for the four backend stacks (format: `$AUDIT_CORE_ROOT/skills/audit-code-scan/references/pattern-file-format.md`).
- `evals/` - prompts, a small .NET fixture with planted issues and one safe query, and the expectations.

Atomic scripts this skill calls (installed next to it, not bundled):

- `$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py` - stack detection (honours `audit/stack.json`).
- `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py` - pattern-driven automated pass.
- `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py` - init / add / validate / md / summary for findings.json.
