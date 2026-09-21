# Pattern file format

Owned by `audit-code-scan`. Every consumer skill keeps its own pattern files under
`<consumer-skill>/scripts/patterns/<stack-id>.json`. This skill only defines the
shape and runs them.

## Schema

A JSON array. A top-level object with a `patterns` array is also accepted.

```json
[
  {
    "id": "RAW-SQL-CONCAT",
    "pattern": "FromSqlRaw\\s*\\(\\s*\\$?\"[^\"]*\"\\s*\\+",
    "globs": ["*.cs"],
    "severity_hint": "High",
    "description": "Raw SQL built by string concatenation",
    "reference": "CWE-89",
    "ignore_case": false
  }
]
```

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | Upper-case kebab id, unique within the file. Prefix by theme, like `SQL-`, `CMD-`, `PATH-`. |
| `pattern` | yes | Python `re` syntax, applied to one line at a time. Escape backslashes for JSON. |
| `globs` | no | File-name globs such as `*.cs` or `appsettings*.json`. Omit to match every text file the walker reads. |
| `severity_hint` | no | Critical, High, Medium, Low or Info. A starting point for the consumer; it is not a rating. Default Medium. |
| `description` | no | What the pattern looks for, in one line. |
| `reference` | no | CWE, ASVS or OWASP id the finding would carry. |
| `ignore_case` | no | Default true. Set false for case-sensitive APIs. |

## Writing good patterns

- **Match the risky shape, not the API name alone.** `FromSqlRaw(` with concatenation
  is a candidate; `FromSqlRaw(` with `{0}` parameters is not. When that distinction
  needs more than one line, keep the broad pattern and let the manual trace decide.
- **Use `(?!...)` for common safe forms** to cut false positives. For example,
  `requests\.get\((?![^)]*timeout)` matches only calls without a timeout.
- **Anchor with `^[ \t]*`, never `^\s*`, in multi-line mode.** `\s` also matches
  newlines. Patterns run per line, so plain `^` is usually enough.
- **Absence checks:** a pattern that should find a marker, such as a CSP header or
  correlation-id middleware, uses an id ending in `-PRESENT`. The consumer treats a zero
  count as the finding.
- **Keep ids stable.** Consumers and evals refer to them by id.

## Validating a pattern file

```bash
python -c "import json,re,sys; [re.compile(p['pattern']) for p in json.load(open(sys.argv[1]))]" scripts/patterns/dotnet.json
python ../audit-code-scan/scripts/grep_scan.py evals/files/<fixture> --patterns scripts/patterns/dotnet.json
```

The first command proves every regex compiles. The second proves the planted
fixture issues produce hits.

## Patterns Python rejects

`grep_scan.py` compiles every pattern when a file loads, so one invalid regex stops the whole
pattern file. Three shapes have caused this; each has an equivalent that works:

- **Variable-width look-behind.** `jwt\.sign\s*\([^;]*\)(?<!expiresIn[^;]{0,80})\s*;` fails.
  Use a negative look-ahead from the opening bracket instead:
  `jwt\.sign\s*\((?![^;]*expiresIn)[^;]*\)\s*;`.
- **Look-behind on a call's options.** `cookies\(\)\.set\s*\([^)]*(?<!httpOnly:\s*true)\)` fails.
  Use `cookies\(\)\.set\s*\((?![^)]*httpOnly:\s*true)[^)]*\)`.
- **Inline flags mid-pattern.** `(?i)A|(?i)B` fails on Python 3.11 and later. Remove the inline
  flags and set `"ignore_case": true` on the rule instead.

The validation command above catches all three before a scan runs.
