# audit-findings-rollup contract

Consumers code against this file. The producer is `scripts/findings_rollup.py`.

## Files

| Artifact | Path | Written by |
|---|---|---|
| Rollup (machine) | `audit/evidence/audit-findings-rollup/rollup.json` | `rollup` subcommand, `write_rollup()` |
| Rollup (human) | `audit/evidence/audit-findings-rollup/rollup.md` | same |
| De-duplicated findings file | the file passed to `dedupe --write` (rewritten in place) | `dedupe --write` |

Nothing is ever written inside `audit/findings/` except by `dedupe --write`, and that
subcommand only rewrites the one file its caller names. `write_rollup()` raises
`ValueError` for any output directory under an `audit/findings` path.

## Risk-acceptance input

A JSON list of risk-acceptance records; the required fields are defined in
audit-production-readiness-checklist's `references/go-no-go-rules.md`. It has no default
location, so the caller passes the path.

```json
[
  {"id": "TENANT-002", "accepted_by": "Sara Malik, Head of Engineering", "date": "2026-09-05",
   "reason": "Single-tenant pilot until INV-812 ships.", "expires": "2026-12-31"}
]
```

- **Required, non-empty:** `id`, `accepted_by`, `date`, `reason`. A record missing any of
  them is `invalid`.
- **`expires`:** optional, `YYYY-MM-DD`. When it is before `as_of` the record is `expired`.
  When it is not a date the record is `invalid`.
- **Other keys:** kept verbatim, for example `compensating_control_verified_by` or
  `follow_up_ticket` from `go-no-go-rules.md`.
- **Duplicate ids:** the last valid record wins.

## rollup.json (schema_version 1)

| Field | Type | Meaning |
|---|---|---|
| `tool` | `"audit-findings-rollup"` | producer |
| `schema_version` | int | `1`; see stability promise |
| `generated_at` | ISO-8601 UTC | when built |
| `as_of` | `YYYY-MM-DD` | date acceptances were checked against |
| `audit_dir` | string | absolute path of the audit workspace read |
| `sources.findings[]` | `{file, skill, findings, has_findings_array}` | each findings file read; `file` is `audit/findings/<name>` |
| `sources.status[]` | `{file, skill, status}` | each status file read |
| `sources.acceptances` | string or null | acceptance file path as given |
| `sources.expected_skills` | list or null | skills that should have run |
| `sources.expected_source` | `"caller"`, `"audit/plan.json"` or null | where that list came from |
| `parse_errors[]` | `{file, error}` | unreadable findings, status or acceptance files |
| `ignored_files[]` | `{file, reason}` | underscore-prefixed findings files, or files for skills excluded by the caller |
| `summary.raw` | severity map | non-false-positive findings before merging |
| `summary.deduplicated` | severity map | after merging by `root_cause_key` |
| `summary.open` | severity map | deduplicated minus findings covered by a valid acceptance |
| `summary.merged` | int | `sum(raw) - len(findings)` |
| `summary.false_positives` | int | findings with `confidence: false-positive` |
| `summary.cross_skill_groups` | int | merged groups spanning more than one skill |
| `summary.risk_accepted` | int | deduplicated findings fully covered by valid acceptances |
| `verdict` | object | see below |
| `critical_high[]` | row | every deduplicated Critical/High, accepted ones included; sorted severity, skill, id |
| `risk_accepted[]` | row | every deduplicated finding (any severity) fully covered by a valid acceptance |
| `acceptances.valid[]` | record | valid acceptance records |
| `acceptances.expired[]` | `{record, why}` | expiry before `as_of` |
| `acceptances.invalid[]` | `{record, why}` | missing field, bad `expires`, not an object |
| `acceptances.unmatched[]` | record | valid records whose id matches no non-false-positive finding |
| `skills` | object | see below |
| `groups[]` | `{root_cause_key, severity, primary{skill,id}, members[{skill,id,severity,title,location}], skills[], cross_skill}` | root causes with 2+ members; members in file order |
| `findings[]` | merged finding | every deduplicated finding; sorted severity, confirmed before likely, id, skill |
| `false_positives[]` | `{skill, id, severity, title, location, impact}` | excluded findings (impact usually says why) |

Severity map: `{"Critical": n, "High": n, "Medium": n, "Low": n, "Info": n}`, always all
five keys. An unknown severity is counted as `Info`.

### verdict

| Field | Meaning |
|---|---|
| `verdict` | exactly `"NO-GO"`, `"CONDITIONAL GO"` or `"GO"`, never prefixed |
| `reason` | one sentence with the open counts that decided it, plus how many Critical/High are covered by acceptance |
| `caveats[]` | strings naming failed, not-run, skipped, unfinished and limited-access skills, unreadable files and expired acceptances; never changes `verdict` |
| `open` | severity map of open findings |
| `accepted` | severity map of accepted findings |
| `blockers[]` | `{id, skill, severity, title, location, merged_ids, acceptance}` for every open Critical/High; `acceptance` is `none`, `expired` or `partial` |

Rule: `NO-GO` if `open.Critical + open.High > 0`; else `CONDITIONAL GO` if
`open.Medium + open.Low > 0`; else `GO`.

### row (critical_high, risk_accepted)

`{id, skill, severity, title, location, confidence, root_cause_key, merged_ids, open, acceptance}`

- `location`: `file[:line]`, where `file` defaults to `.`.
- `merged_ids`: the other ids merged into this finding (primary id excluded).
- `confidence`: defaults to `confirmed` when absent.
- `acceptance`: `{status, records[], expired[], uncovered_ids[]}`. `status` is one of:
  - `accepted`: every id covered.
  - `partial`: some ids covered.
  - `expired`: no valid record, but at least one expired one.
  - `none`: no record at all.

### skills

| Field | Meaning |
|---|---|
| `by_skill[]` | `{skill, status, reason, skip_kind, limited_access[], status_file, findings_file, counts_raw, counts_rollup, critical_high_ids[]}` for every skill with a findings file, a status file or in the expected list. `status` is null without a status file. `counts_rollup` attributes a merged finding to its primary's skill. |
| `completed[]` | names with status `completed` (limited access included) |
| `failed[]` | `{skill, reason}` |
| `skipped[]` | `{skill, reason, skip_kind, skipped_by}` |
| `limited_access[]` | `{skill, reason, items[]}`: completed with a non-empty `limited_access` list, or a `reason` starting `limited access:` |
| `not_run[]` | `{skill, reason}`: expected, but no status file and no findings file |
| `other_status[]` | `{skill, status, reason}`: any other status value, such as `running` |
| `no_status_file[]` | names with a findings file but no status file |
| `unreadable[]` | `{file, error}` for findings and status files that could not be parsed |

### merged finding (in `findings[]` and in `dedupe` output)

It is the primary's finding object with every original field, plus:

| Field | Meaning |
|---|---|
| `severity` | highest severity in the group (the primary's) |
| `references`, `tags` | union over members, first-seen order |
| `evidence` | each member's block as `file:line\n<evidence>`, joined by a blank line (the finding-writer format). When a member's evidence already begins with exactly that `file:line` (not followed by another digit), the evidence is used as is, so the location is not repeated. |
| `extra.merged_ids` | every id in the group, primary first, then by severity. Earlier merges are carried over. |
| `extra.locations` | every member's `location` object (`{file, line, symbol}`) |
| `extra.primary_evidence` | the primary's evidence text, unmodified |
| `extra.merged_members` | `{skill?, id, severity, title, location}` per member; `skill` is present only in rollup (many-file) use |

Only in `rollup.json` findings (not in a findings file):

| Field | Meaning |
|---|---|
| `skill` | the skill of the file the finding (primary) came from |
| `source_file` | `audit/findings/<name>` |
| `open` | bool |
| `acceptance` | the coverage object described under row |

A finding that did not merge has no `extra.merged_*` keys added.

## Python API

Load the module by file path under a unique module name, the pattern every audit script
uses for atomic skills. Do not put this skill's `scripts/` folder on `sys.path`: several
skills ship scripts with the same file name, so a later bare import could resolve to the
wrong one.

```python
import importlib.util
import os

_SKILLS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_ROLLUP = os.path.join(_SKILLS, "audit-findings-rollup", "scripts", "findings_rollup.py")
_spec = importlib.util.spec_from_file_location("audit_findings_rollup", _ROLLUP)
fr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fr)
```

| Function | Returns |
|---|---|
| `load_findings(source=".", skip_underscore=True, exclude_skills=())` | `{sources, documents[{path, file, skill, doc}], findings, parse_errors, ignored_files}`. `source` is a repo root, an `audit/` dir, a findings dir, one file or a list of files. `findings` are copies carrying `skill` and `source_file`. `documents[].doc` is the raw, mutable document. |
| `load_status(source=".")` | `{skills: {name: {skill, status, reason, skip_kind, skipped_by, limited_access, started_at, finished_at, file, raw}}, sources, parse_errors}` |
| `load_acceptances(source=None, as_of=None)` | `{file, as_of, valid, expired, invalid, parse_error}`. `source` is a path, a list of records or an already-loaded result. `as_of` in the result is a `YYYY-MM-DD` string. An already-loaded result is returned unchanged. |
| `merge_by_root_cause(findings, key="root_cause_key")` | list of findings in input order, merged per the rules above; `key="title"` merges by normalised title |
| `merge_report(findings, key="root_cause_key")` | `[(key, [ids])]` for groups that would merge |
| `severity_counts(findings)` | severity map; false positives excluded |
| `critical_high(findings, acceptances=None, skills=None)` | rows; pass raw findings for one row per finding, merged for deduplicated; `skills` filters by skill name |
| `acceptance_coverage(finding, acceptances)` | coverage object |
| `skill_summary(findings_load, status_load, expected=None)` | the `skills` object (without `counts_rollup`) |
| `verdict(findings, acceptances=None, skills=None)` | the `verdict` object |
| `rollup(source=".", acceptances=None, expected=None, as_of=None)` | the full rollup.json document; writes nothing |
| `render_md(doc)` | rollup.md text |
| `write_rollup(doc, out_dir)` | `(json_path, md_path)`; raises `ValueError` inside `audit/findings` |
| `location_str(finding, symbol=False)` | `file[:line][ (symbol)]` |

Constants: `SEVERITIES`, `NO_GO`, `CONDITIONAL_GO`, `GO`, `ACCEPTANCE_REQUIRED`, `SCHEMA_VERSION`.

### Return types that are not plain JSON

Every return value is built from dicts, lists, strings, ints, bools and `None`, so
`json.dumps` works on it, with these exceptions:

| Where | Python type | Note |
|---|---|---|
| `merge_report()` | list of `(key, [ids])` tuples | `json.dumps` turns each tuple into an array. |
| `write_rollup()` | `(json_path, md_path)` tuple of OS-native path strings | Backslashes on Windows. |

Dates are never returned as `datetime.date`. `load_acceptances()["as_of"]`, `rollup()["as_of"]`
and `generated_at` are ISO strings. Call `date.fromisoformat(acc["as_of"])` when a date object is
needed. The `as_of` argument of `load_acceptances()` and `rollup()` accepts a `date`, a
`datetime` (its date is used), a string starting `YYYY-MM-DD`, or `None` (today, UTC).

`documents[].doc` from `load_findings()` and `skills[name].raw` from `load_status()` are the
parsed documents themselves, not copies. Changing them changes what a later call in the same
process sees.

### Skill identity

Every per-skill key is the document's `skill` field. The file stem
(`audit/findings/<stem>.json`, `audit/status/<stem>.json`) is used only when `skill` is missing
or empty. This applies to:
- `sources.findings[].skill` and `sources.status[].skill`;
- `findings[].skill`, the `load_status()["skills"]` keys and every `skills.*` entry;
- `counts_rollup`, `exclude_skills`, the `skills` filter of `critical_high()`, and `expected`.

A consumer that builds its own lookup, for example of `documents[].doc` for scope or
`target.commit`, must key it by `documents[].skill`, never by the file name. Otherwise the lookup
misses whenever a file is named differently from its `skill` field.

## CLI

| Command | Output | Exit |
|---|---|---|
| `rollup [root] [--audit-dir] [--accepted] [--as-of] [--expected a,b] [--out-dir] [--print]` | writes both files; prints `{json, md, verdict, reason, caveats, summary, parse_errors}` or the full doc with `--print` | 0; 2 when there is no workspace or the output path is refused |
| `verdict [root] [...same inputs] [--text]` | verdict object, or `VERDICT - reason` plus caveat lines | 0 / 2 |
| `counts [root] [--audit-dir] [--accepted] [--as-of]` | the `summary` object | 0 / 2 |
| `dedupe <file> [--key root_cause_key\|title] [--write] [--json]` | `key: merging [ids]` lines or `nothing to merge`, then `wrote <file>` after a write; `--json` prints the merged document | 0; 2 when the file is unreadable |

`dedupe --write` rewrites the file only when something merged. It recomputes `summary`
from the merged findings, excluding false positives.

## Stability promise

- **Additive changes only within schema_version 1.** Existing fields keep their names,
  types and meanings. New fields may appear, so consumers must ignore unknown keys.
- **The verdict words and the rule are fixed.** Changing either is a breaking change.
  It needs the user's decision and a `schema_version` bump, announced in this file.
- **Caveat text is for people.** Its wording may change. Consumers that need the facts
  read `skills.*` and `acceptances.*`, never the caveat text.
- **Function signatures above are stable.** New keyword arguments may be added with
  defaults that keep today's behavior.
