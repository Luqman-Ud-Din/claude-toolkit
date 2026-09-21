---
name: audit-orm-query-and-data-access
description: Reviews ORM and data-access code for N+1 queries, missing eager loading (Include/join fetch/relations/select_related), unbounded select-all queries with no pagination, read queries that leave change tracking on, filtered or sorted columns with no index (cross-checked with audit-db-schema), multi-table writes with no transaction, and inefficient patterns like client-side evaluation, loading whole entities to read one column, and Count() where Any()/exists would do. Use whenever the user asks about ORM performance, EF Core, Hibernate/JPA, Prisma, TypeORM, Sequelize, Django ORM, query-builder or repository code, N+1, lazy loading, slow queries, missing pagination, "GetAll returns everything", data access review, DbContext or repository patterns, or as part of a general performance, scalability, or pre-production audit, even when the user does not name the skill.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-app:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit: ORM queries and data access

Most production slowness lives between the repository method and the database:
a loop that issues one query per row, a list endpoint that returns the table,
a read that tracks ten thousand entities it will never modify. These are
invisible in tests with three rows and obvious at ten thousand. This skill finds
them by reading the code, then tells the team how to turn on query logging so
the numbers confirm it under load.

Read-only rule: never modify the audited code. Write only under `audit/`
(findings, reports, evidence, status).

## Inputs / prerequisites

- Path to the audited backend repository root.
- `audit/stack.json` if `audit-application` already wrote it; otherwise run
  `$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py`.
- Skills from the `audit-core` plugin (reached via `$AUDIT_CORE_ROOT`, exported by that plugin; a sibling `skills/` layout also works): `audit-stack-detection`,
  `audit-code-scan`, `audit-endpoint-inventory` (which itself needs
  `audit-sensitive-data-catalog`) and `audit-finding-writer`.
- Optional: `audit/findings/audit-db-schema.json` (index inventory) for the
  index cross-check; without it, list the filtered/sorted columns you could not
  verify and hand them to `audit-db-schema`.
- Optional: a running instance with query logging on, to confirm N+1 counts.
- Python 3 (stdlib only) for the bundled scripts.

## Workflow

1. **Resolve the stack.** `python "$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py" <repo>`. Open only
   `references/<stack>.md` for the primary backend; it names the ORM (EF Core,
   Hibernate/JPA, Prisma/TypeORM/Sequelize/Mongoose, Django ORM), the exact API
   shapes to grep, the "good" idiom, the query-logging config, and the false
   positives. Unknown stack: `$AUDIT_CORE_ROOT/skills/audit-stack-detection/references/stack-reference-template.md`, and say so.
2. **Automated pass.**
   `python "$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py" <repo> --patterns scripts/patterns/<stack>.json --out audit/evidence/audit-orm-query-and-data-access/hits.json --md audit/evidence/audit-orm-query-and-data-access/hits.md`
   then run `audit-endpoint-inventory`, or reuse
   `audit/evidence/audit-endpoint-inventory/endpoints.json` when the orchestrator
   already produced it:
   `python "$AUDIT_CORE_ROOT/skills/audit-endpoint-inventory/scripts/inventory_endpoints.py" <repo>`.
   Unbounded handlers are the HTTP records with a materialising data call and no
   `Skip/Take`, `Pageable`, `take/skip`, `LIMIT`, or slice anywhere in the handler.
   Write them to this skill's evidence folder (drop `r["kind"] == "http"` to include jobs):

   ```bash
   python - <repo> <<'EOF'
   import json, os, sys
   ev = os.path.join(sys.argv[1], "audit", "evidence")
   doc = json.load(open(os.path.join(ev, "audit-endpoint-inventory", "endpoints.json"), encoding="utf-8"))
   rows = [{"file": r["file"], "line": r["line"], "handler": r["handler"], "route": r["path"],
            "data_call": r["data_access"]["materializing_calls"][0]["text"],
            "data_call_line": r["data_access"]["materializing_calls"][0]["line"],
            "paging_seen": False, "kind": "handler"}
           for r in doc["endpoints"]
           if r["kind"] == "http" and r["data_access"]["materializing_calls"] and not r["data_access"]["paging_seen"]]
   out = os.path.join(ev, "audit-orm-query-and-data-access")
   os.makedirs(out, exist_ok=True)
   json.dump({"root": doc["root"], "stacks": doc["stacks"], "count": len(rows), "rows": rows},
             open(os.path.join(out, "unbounded.json"), "w", encoding="utf-8"), indent=2)
   with open(os.path.join(out, "unbounded.md"), "w", encoding="utf-8") as fh:
       fh.write("| Route | Handler | Location | Data call |\n|---|---|---|---|\n")
       for r in rows:
           fh.write(f"| {r['route']} | {r['handler']} | `{r['file']}:{r['data_call_line']}` | `{r['data_call'][:100].replace('|', '/')}` |\n")
   print(len(rows), "unbounded handlers")
   EOF
   ```

   Repository and manager methods that return a materialised collection are the
   `UNBOUNDED-REPO-COLLECTION` grep hits. Grep cannot see paging applied a few
   lines later, so check each hit for paging by hand. Pattern ids map to
   the classes in `references/antipattern-catalog.md` (NPLUS1, UNBOUNDED,
   TRACKING, INDEX, TXN, INEFFICIENT).
3. **Manual trace of the highest-risk flows.** In order: (a) every list endpoint
   the frontend hits on page load (the main grid, dashboard counters) - is it
   paged, does it project, how many queries per request; (b) every loop whose body
   touches a repository/DbContext/queryset - N+1 unless the collection was loaded
   with the parent; (c) every write path that touches two or more tables (order +
   lines + stock movement) - one transaction or none; (d) reports/exports - do they
   stream or materialise; (e) filters and `ORDER BY` columns - compare with the
   index list from `audit-db-schema`. Save traces to
   `audit/evidence/audit-orm-query-and-data-access/<id>-trace.md`.
4. **Write findings** with `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py` (`init` once, `add` per finding,
   `md` to render). Severity per `audit-finding-writer/references/severity-rubric.md`:
   N+1 or unbounded list on the main page is High; the same on an admin-only
   report is Medium; tracking on a small read is Low.
5. **Produce the outputs**: findings, `audit/reports/audit-orm-query-and-data-access.md`
   using the template below (unbounded-endpoint list, index cross-check table,
   query-logging config from `references/query-logging.md`), and
   `audit/status/audit-orm-query-and-data-access.json`
   (`{"skill","status":"completed|failed|skipped","reason","started_at","finished_at"}`).
6. **List what was not checked**: raw SQL / stored procedures (owned by
   `audit-injection-vulnerabilities` for safety, by `audit-db-schema` for plans),
   query plans (need a live DB), index existence if `audit-db-schema` has not run,
   and any repository whose base class you could not open.

## Finding format

Write findings using `audit-core:audit-finding-writer`, with ID prefix `ORM`.
Use its canonical schema and severity rubric. Topic-specific field guidance:

- **Reference:** CWE-nnn, ASVS-x.y.z, OWASP-A0n:2021 (use what applies; see references/<stack>.md)


Recurring references: CWE-770 (allocation without limits), CWE-400 (resource
consumption), CWE-1049 (excessive data query operations in a loop), CWE-1072
(data resource access without use of connection pooling), CWE-362/CWE-662
(transaction/atomicity), ASVS-12.1.1, ASVS-13.x.

## Output template (`audit/reports/audit-orm-query-and-data-access.md`)

```markdown
## audit-orm-query-and-data-access findings
| Critical | High | Medium | Low | Info |
|---|---|---|---|---|
| n | n | n | n | n |

### Scope
- Stack / ORM: <stack>, <ORM + version from manifest>
- Automated pass: <N> hits across <M> patterns; <K> unbounded handlers from audit-endpoint-inventory; <R> UNBOUNDED-REPO-COLLECTION hits (paging checked by hand)
- Manually traced: <list endpoints / repositories>

### Findings
<one block per finding, ordered by severity>

### Endpoints returning unbounded collections
| Endpoint (route) | Handler | Data call | Table / entity | Paging present | Projection | Est. rows in prod | Finding |
|---|---|---|---|---|---|---|---|
| GET /api/products | ProductsController.GetAll | `_db.Products.ToListAsync()` | Products | no | full entity | 50k | ORM-002 |

### Query-per-request estimates (N+1)
| Endpoint | Outer query | Per-row queries | Rows typical | Queries per request | Finding |
|---|---|---|---|---|---|

### Index cross-check (with audit-db-schema)
| Query location | Filtered / sorted columns | Index found (audit-db-schema) | Action |
|---|---|---|---|
| ProductsController.Search:41 | Products(CompanyId, BranchId, Name) | none on Name | ORM-004 -> DB-xxx |

### Transactions around multi-table writes
| Write path | Tables touched | Transaction | Finding |
|---|---|---|---|

### Recommended query logging (verify under load)
<paste the block for this ORM from references/query-logging.md: config key, sample output, what to count>
Pass criteria: no endpoint exceeds 10 queries per request; no single query returns > 1000 rows without paging; slow-query log (> 200 ms) empty for list pages.

### Not checked
- <item> - <reason>
```

## Examples

**Input (grep hit, EF Core):**
`Managers/SaleManager.cs:88: foreach (var line in sale.Lines) { var p = await _db.Products.FirstAsync(x => x.Id == line.ProductId); ... }`

**Output:**
```markdown
### [High] ORM-001 - Product looked up per sale line inside a loop (N+1)
- **Location:** `Managers/SaleManager.cs:88` (CalculateTotals)
- **Confidence:** confirmed
- **Evidence:**

```csharp
foreach (var line in sale.Lines)
    var p = await _db.Products.FirstAsync(x => x.Id == line.ProductId);   // one round-trip per line
```

- **Impact:** A 200-line sale issues 201 queries; at checkout volume this is the dominant database load and the reason POS saves take seconds. High: hit on the main sales flow by every user.
- **Remediation:** Load once: `var ids = sale.Lines.Select(l => l.ProductId).ToList(); var products = await _db.Products.AsNoTracking().Where(p => ids.Contains(p.Id)).ToDictionaryAsync(p => p.Id);` then look up in memory; or `Include(s => s.Lines).ThenInclude(l => l.Product)` when loading the sale.
- **Reference:** CWE-1049, ASVS-12.1.1
```

**Input (unbounded handler row from audit-endpoint-inventory):** `GET /api/products -> ProductsController.GetAll -> _db.Products.ToListAsync()` (no Skip/Take, full entity).

**Output:** `[High] ORM-002 - Product list endpoint returns the whole table
untracked-off and unpaged` with remediation `Skip/Take` + `Select` projection +
`AsNoTracking()`, CWE-770; add the row to the "Endpoints returning unbounded
collections" table.

## Bundled files

- `references/<stack>.md` - ORM API shapes, good idiom, trace checklist, false positives, tooling per stack (dotnet/EF Core, java-spring/Hibernate, node-express/Prisma-TypeORM-Sequelize-Mongoose, python-django; angular/react/vue describe the client-side pagination and over-fetch contract); to add a stack, copy `$AUDIT_CORE_ROOT/skills/audit-stack-detection/references/stack-reference-template.md`.
- `references/antipattern-catalog.md` - the six classes with proof-of-defect / proof-of-safety and severity guidance.
- `references/query-logging.md` - query logging config per ORM (EF Core, Hibernate/JPA, Prisma/TypeORM/Sequelize, Django ORM) and what to count.
- `scripts/patterns/<stack>.json` - grep patterns for the automated pass, including `UNBOUNDED-REPO-COLLECTION` for repository methods returning materialised collections.
- Atomic scripts this skill calls: `$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py` (stack), `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py` (automated pass), `$AUDIT_CORE_ROOT/skills/audit-endpoint-inventory/scripts/inventory_endpoints.py` (handlers with a materialising call and no paging), `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py` (findings I/O).
- `evals/` - prompts and a fixture with an N+1 loop, a GetAll with no paging, and a tracked read query, plus correctly paged/projected negatives.
