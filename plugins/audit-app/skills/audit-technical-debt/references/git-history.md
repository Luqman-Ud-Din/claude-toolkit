# Git history inputs

`churn.py`, `todo_age.py`, `docs_check.py` and `debt_score.py` read history through
`$AUDIT_CORE_ROOT/skills/audit-git-history/scripts/githist.py`, owned by the `audit-git-history` skill, which must be
installed next to this one. It runs only read-only git commands (`log`, `blame`, `rev-parse`
and similar). Its functions, return shapes and CLI are in
`$AUDIT_CORE_ROOT/skills/audit-git-history/references/githist-contract.md`.

## Modes

| Mode | When | Flags | Effect |
|---|---|---|---|
| git | the repo is a work tree and git is on PATH | (default) | `git log --numstat` for churn, `git log -p -U0` hunks for function churn on the top files, `git blame --line-porcelain` for TODO ages |
| synthetic | no `.git` (fixtures, source exports, zip uploads) | `--history FILE` | commits, touched functions and blame ranges come from a JSON file |
| none | no history available or wanted | `--no-git` (or automatic when not a work tree) | churn is empty, hotspot list is empty, ages are null; complexity-only ranking; the report says so under Not checked |

`--as-of YYYY-MM-DD` fixes the reference date for ages and windows (default: the synthetic
history's `head_date`, else today). Use it to make runs reproducible. In git mode, commits
dated after the as-of date (plus one day) are outside the window.

## Pitfalls to check before trusting the numbers

- **Shallow clones** (CI checkouts with `fetch-depth: 1`): `githist.py` detects them and
  says so in `history.reason`. Churn and blame are truncated; audit a full clone.
- **Bulk reformat or rename commits** make every line look new and every file hot. List
  them in `.git-blame-ignore-revs` (honoured automatically for blame) and start the churn
  window after them with `--since-days`.
- **Monorepo subfolders**: run with the subfolder as root; paths are made relative to it.
- **Squash-merge workflows** undercount churn (one commit per PR); compare hotspots by
  relative rank, not absolute counts.
- **Function churn** from hunks is mapped onto the current function spans, so it is
  approximate for files that were heavily restructured inside the window.

## Synthetic history format

The format (`head_date`, `commits[]` with `files[].functions` or `files[].hunks`, and
per-file `blame` ranges) is defined in the "Synthetic history format" section of
`$AUDIT_CORE_ROOT/skills/audit-git-history/references/githist-contract.md`, including how to export one from a
repository you cannot run the scripts in.

- `functions` (exact names) or `hunks` (`[[start, end], ...]` new-side line ranges) give
  function-level churn here; without either, the file-level score is used.
- Blame picks the smallest range containing the line; files without blame use the date
  of the newest commit touching them (marked `approx`).

The eval fixture uses `evals/files/synthetic-git-history.json` because a skill cannot ship
a `.git` directory.
