# Injection classes, sources, sinks, and the confidence rubric

Use this file for cross-stack reasoning; the per-stack files name the concrete APIs.

## Classes and pattern-id prefixes

| Prefix | Class | Sink shape | Typical CWE | ASVS |
|---|---|---|---|---|
| SQL | SQL injection | query text built from strings, dynamic ORDER BY / table names, `EXEC(@sql)` | CWE-89 | 5.3.4, 5.3.5 |
| NOSQL | NoSQL / query-object injection | Mongo `$where`, filter objects built from raw body JSON, `$regex` from input | CWE-943 | 5.3.4 |
| CMD | OS command injection | shell invoked with a string, `sh -c`, `cmd /c`, arguments interpolated | CWE-78 | 5.3.8 |
| PATH | Path traversal / arbitrary file access | file open/read/write/delete/serve using a request-supplied name | CWE-22 | 12.3.1 |
| LDAP | LDAP injection | DN or filter string built from input | CWE-90 | 5.3.7 |
| XPATH | XPath / XML query injection | `SelectNodes("//user[name='" + n + "']")` | CWE-643 | 5.3.10 |
| TMPL | Server-side template injection | template *source* (not data) built from input; `Razor.Parse(userString)`, Jinja `Template(user)` | CWE-1336 | 5.2.5 |
| SSRF | Server-side request forgery | outbound HTTP/URL fetch to a user-supplied URL or host | CWE-918 | 12.6.1 |
| DESER | Unsafe deserialization | type-carrying deserializers on untrusted bytes (`BinaryFormatter`, `ObjectInputStream`, `pickle`, `yaml.load`, `TypeNameHandling.All`) | CWE-502 | 5.5.1-5.5.3 |

Pattern ids in `scripts/patterns/*.json` start with the prefix (`SQL-RAW-CONCAT`,
`CMD-SHELL-STRING`, ...). Use the lower-case class as the finding `tag`.

## Sources (where "user-controlled" comes from)

1. Route, query string, headers, cookies, body fields, multipart file names.
2. Values read from the database that a user wrote earlier (second-order injection: a stored display name used in a later dynamic query).
3. Queue / webhook / integration payloads (Shopify, SMS callbacks, FBR responses).
4. Configuration and environment - treat as trusted unless the app lets admins edit it in a UI.
5. Anything derived from the above without a structural transform (a `string.Format` still carries the taint; an integer parse or an allow-list lookup removes it).

## What removes the taint

- Parameterized queries / bound variables (the value never enters the query text).
- Allow-list lookup returning a constant (`SortColumns[key]`), or a strict enum parse.
- Numeric / GUID / date parsing.
- For paths: `GetFileName` / `basename` **plus** resolving under a fixed root and checking the resolved prefix.
- For SSRF: host allow-list compared after URL parsing, DNS pinning or egress proxy; scheme restricted to http(s).
- For CMD: argument-array invocation with no shell, argument allow-list.
- For DESER: type-restricted binder / whitelist, or switching to a data-only format (JSON with no polymorphic type handling).

Escaping functions (`Replace("'", "''")`, `shlex.quote`) remove taint only when applied to the exact context the sink uses; treat them as `likely` unless you verified the context.

## Confidence rubric

| Label | Rule |
|---|---|
| confirmed | You traced a source in the list above to the sink with no taint-removing transform, and the endpoint or job that reaches it exists. |
| likely | The sink takes a variable that is user-controlled by name or by convention (`model.`, `request.`, `req.body`) but the trace passes through code you could not open (stored procedure body, external package, reflection, a queue consumer), or you could not confirm the endpoint is reachable. |
| false-positive | Input is a constant, an enum, or a parsed number; or the sink is genuinely parameterized (`{0}` + args, `$"..."` inside `FromSqlInterpolated`, `?` placeholders with a bound list); or a verified allow-list stands in front. Record the reason in `evidence`. |

`likely` never lowers severity; report the severity a confirmed hit would have and ask the reviewer to close the gap.

## Severity anchors

- Critical: SQLi/CMD/DESER reachable without authentication, or reachable by any tenant in a shared-database multi-tenant app (cross-tenant read is a full compromise).
- High: SQLi/CMD/DESER/SSRF-to-internal-network behind ordinary authentication; path traversal that can read secrets (`appsettings`, `.env`) or write files.
- Medium: path traversal confined to a public asset folder; SSRF limited to GET with response not returned; dynamic ORDER BY where the DB user is read-only and single-tenant; XPath on non-sensitive XML.
- Low: dangerous API used with a constant today but no guard (a maintenance risk); template engine with auto-escaping off on trusted data.
- Info: verified false positives worth keeping (a `FromSqlRaw` with placeholders that a future reader might mistake for a bug).
