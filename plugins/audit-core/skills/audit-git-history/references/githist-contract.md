# githist contract

Owned by `audit-git-history`. Consumers write their code against this file only. Contract version: `1.0`
(`githist.CONTRACT_VERSION`, echoed as `contract` in every CLI envelope).

## Stability promise

- Within `1.x`, function names, parameter names and their order, and every field listed
  here keep their meaning. Fields are only ever added.
- Consumers must ignore keys they do not know.
- The synthetic history format only gains optional keys. A file valid for
  `audit-technical-debt`'s original `githist.py` stays valid and gives the same answers.
- `History.reason` strings are human text, not an API. Branch on `mode`, `shallow` and
  `not_checked()` instead. The exact strings for `--no-git`, not-a-work-tree, git-missing
  and shallow are kept from the original module, because consumer reports print them.
- A breaking change bumps the major version and is announced in this file.

## Import snippet

```python
import importlib.util
import os
import sys

_SKILLS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_GITHIST = os.path.join(_SKILLS, "audit-git-history", "scripts", "githist.py")
if not os.path.exists(_GITHIST):
    sys.exit("audit-git-history must be installed next to this skill (expected " + _GITHIST + ")")
_spec = importlib.util.spec_from_file_location("audit_git_history_githist", _GITHIST)
githist = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = githist
_spec.loader.exec_module(githist)
```

This is the loader `audit-technical-debt/scripts/churn.py` uses. It loads the module by
file path under the unique name `audit_git_history_githist`.
- **No `sys.path` import.** Never put `audit-git-history/scripts` on `sys.path` and then
  `import githist`. A stray `githist.py` in another skill's `scripts/` folder, or a leftover
  local copy, could be imported instead.
- **Several atomic modules.** A script that loads more than one can wrap these lines in a
  helper, as `audit-technical-debt/scripts/debt_score.py` does with `_load_sibling`.

`githist` itself imports `repo_walk` from `audit-code-scan`, so both skills must be installed.

## Modes

| `mode` | When | Behaviour |
|---|---|---|
| `git` | git on PATH and root inside a work tree | Real queries. `shallow` is true for a shallow clone. |
| `synthetic` | `history_file` given | Answers come from the JSON file (format below). `shallow` comes from `repo.shallow`. |
| `none` | `no_git=True`, git missing, or not a work tree | Every query returns an empty result. `not_checked()` explains why. |

`not_checked()` returns `[{item, reason}]`:
- `{"item": "git history", ...}` when mode is `none`.
- `{"item": "full git history", ...}` when `shallow` is true.

Consumers copy these entries into their own Not checked list. An empty result in mode
`none`, or any history-depth answer from a shallow clone, must never be reported as "zero".

## `History(root, history_file=None, no_git=False)`

| Attribute | Type | Meaning |
|---|---|---|
| `root` | str | Absolute root path. |
| `mode` | str | `git`, `synthetic` or `none`. |
| `reason` | str | Human explanation of the mode. |
| `shallow` | bool | Shallow clone, or synthetic `repo.shallow`. |
| `prefix` | str | Root's path below the repo top, with a trailing `/`; `""` at the top. Output paths drop it. |
| `git_available` | bool | `git` found on PATH, whatever the mode. |
| `data` | dict or None | The loaded synthetic document. Commits are sorted newest first and carry a private `_date`. |

Conventions for every method:
- Dates are timezone-aware UTC `datetime` objects. `jsonable()` turns them into
  `YYYY-MM-DDTHH:MM:SSZ` strings.
- `hash` is the first 10 characters of the commit id (the synthetic id as written), and
  `hash_full` is the whole id.
- Paths are forward-slash and relative to `root`.
- `paths` is a list of pathspecs. In git they are passed through, so `:(glob)**/.env`
  works. In synthetic mode each spec matches an exact path, a directory prefix or an
  fnmatch glob, and `:(glob)` and `**/` are accepted.
- The window is `since_days` (days before `as_of`) and `last_n` (newest N). Both apply
  when both are given; neither means all history. `as_of` defaults to
  `default_as_of()`: the synthetic `head_date`, else its newest commit, else now. Git
  windows also exclude commits after `as_of` + 1 day, matching synthetic mode.

## Methods

| Method | Returns |
|---|---|
| `default_as_of()` | `datetime` |
| `not_checked()` | `[{item, reason}]` |
| `commits(since_days=None, last_n=None, as_of=None, paths=None, all_refs=False, merges=False, with_files=True)` | `[Commit]`, newest first |
| `churn(since_days=None, last_n=None, as_of=None, paths=None, all_refs=False, follow_renames=False)` | `[FileChurn]`, sorted by commits desc, then path |
| `hunks_for_file(relpath, since_days=None, last_n=None, as_of=None)` | `{hash: [(start, end), ...]}`: new-side changed line ranges per commit, merges excluded. A commit can map to `[]`, for example a pure rename. |
| `range_churn(relpath, ranges, since_days=None, last_n=None, as_of=None)` | `[{start, end, commits, hashes}]`, one entry per `(start, end)` in `ranges` |
| `line_info(relpath, line)` | `BlameLine` dict (`date, author, commit, approx`, plus git-only keys) or `None` |
| `blame(relpath, start=None, end=None, as_of=None)` | `[BlameEntry]`, one per line in `[start, end]`; `end` defaults to the file length |
| `History.group_blame(entries)` (static) | `[{start, end, lines, commit, author, date, age_days, approx, boundary, summary}]` |
| `last_change(relpath)` | `{date, author, commit}` of the newest commit touching a file or directory prefix, or `None` |
| `added_lines(paths=None, all_refs=True, max_commits=2000, since_days=None, as_of=None, match=None, stats=None)` | generator of `AddedLine` (`source: "history"`) |
| `tree_lines(paths=None, match=None, **repo_walk_kwargs)` | generator of `AddedLine` (`source: "tree"`) over `repo_walk.iter_files(root, ...)` |
| `tickets(since_days=None, last_n=None, as_of=None, paths=None, all_refs=False, merges=True, subject_only=False, include_urls=False)` | `{commits: [TicketCommit], summary: {commits, with_ref, without_ref, by_kind}}` |
| `path_history(pathspec, all_refs=True)` | `[PathRecord]`; `[]` means nothing matching was ever committed |
| `refs_containing(rev)` | `RefsRecord` |
| `info(tags_limit=20)` | `RepoInfo` |

### Module functions and constants

| Name | Returns / meaning |
|---|---|
| `add_history_args(argparse_parser)` | Adds `--history`, `--no-git`, `--as-of` (unchanged from the original module). |
| `resolve_as_of(hist, as_of_arg)` | `datetime`: the parsed `--as-of`, else `hist.default_as_of()`. |
| `parse_date(value)` | UTC `datetime` from ISO text, a `YYYY-MM-DD` prefix, epoch seconds or a `datetime`; `None` if unparseable. |
| `iso(dt)` | `"YYYY-MM-DDTHH:MM:SSZ"` or `None`. |
| `jsonable(obj)` | Deep copy that is safe for `json.dumps`. |
| `ticket_refs(text, include_urls=False)` | `[{kind, id, match, start}]`, in text order, de-duplicated by `id`. |
| `remote_provider(url)` | `github`, `gitlab`, `azure`, `bitbucket`, `other` or `none`. |
| `is_git_repo(root)` | bool. |
| `TICKET_RULES`, `NOT_TICKET_PREFIXES`, `SHALLOW_REASON`, `WORKING_TREE`, `CONTRACT_VERSION` | Fixed rule data and strings. |

## Record shapes

**Commit**:

```
{hash, hash_full, date, author, email, parents: [hash10...], subject, message,
 files: [{path, old_path, status, added, deleted, binary, functions, hunks}]}
```

- `files` is `[]` for merges, and when `with_files=False`.
- `status` is the first letter of git's raw status (`A`, `M`, `D`, `R`, `C`, `T`), or
  whatever the synthetic file says, else `None`.
- `old_path` is set for `R` and `C`.
- `path` is the rename-resolved new path.
- `added` and `deleted` are 0 for binary files (`binary: true`).
- `functions` and `hunks` come from synthetic data only; they are `None` in git mode.
- `email` is `""` in synthetic mode unless given.

**FileChurn**:

```
{path, commits, added, deleted, authors (count), author_names [sorted], first_change, last_change, renamed_from [paths]}
```

- A commit counts once per path.
- With `follow_renames`, commits made under older names are folded into the newest
  name, and those names are listed in `renamed_from`.

**BlameEntry**:

```
{line, commit, author, date, age_days, approx, boundary, uncommitted, summary, original_path}
```

- `commit` is `None` when the line has no answer.
- `approx` is synthetic only: no blame range covered the line, so the newest commit
  touching the file was used.
- `boundary` means a boundary commit: the root commit, or the cut-off of a shallow clone.
- `uncommitted` means a working-tree change.
- `summary` and `original_path` come from git only; `original_path` is the path the line
  had in its origin commit, so it resolves renames.
- `age_days` is `(as_of - date).days`.

**AddedLine**:

```
{hash, hash_full, author, date, file, line, text, source}
```

- `line` is the new-side line number.
- `text` has no diff prefix and no line ending.
- History lines come from `git log -p --cc -U0 -M --no-textconv` over `--all` (unless
  `all_refs=False`), newest first, capped at `max_commits` commits. Merge commits yield
  only lines new to every parent.
- Tree lines have `hash` and `hash_full` set to `"(working tree)"`, `author` `""` and
  `date` `None`.
- `match` is a regex, as a string or compiled, tested against `text`.
- `stats["commits_scanned"]` is complete once the generator is exhausted.

**TicketCommit**:

```
{hash, hash_full, date, author, parents (count), subject, refs: [{kind, id, match, in}]}
```

`kind` values and their `id` forms:

| `kind` | `id` form | Matches |
|---|---|---|
| `jira` | `ABC-123` | Upper-case key of 2-10 characters starting with a letter, unless the key is in `NOT_TICKET_PREFIXES` (UTF, SHA, ISO, CVE, ...). |
| `github` | `#123` | `#` followed by digits, not preceded by a word character or `#`. |
| `azure` | `AB#123` | `AB#` followed by digits. |
| `closing-keyword` | `#123` | `fixes`, `closes` or `resolves` followed by a bare number (case-insensitive). |
| `url` | the URL | Only when `include_urls=True`. |

- `in` is `subject` or `body`; a body reference with an id already in the subject is dropped.
- `merges=True` by default, because merge subjects often carry the PR number.

**PathRecord**:

```
{path, ever_committed, state, tracked_at_head, exists_in_worktree, added_in, deleted_in, renamed_to,
 events: [{hash, hash_full, date, author, status, path, old_path, subject}]}
```

- `state` values:
  - `tracked`: in the HEAD tree.
  - `deleted`: the newest event is `D`.
  - `renamed`: the newest event moved this path elsewhere; see `renamed_to`.
  - `not-at-head`: the path exists only on other refs.
- `added_in` is the oldest add, and `deleted_in` the newest delete; both are 10-character hashes.
- `events` are newest first, across all refs by default, with merges excluded.
- In git, a `D` under a path filter is checked against the whole commit, so a rename is
  not reported as a deletion.

**RefsRecord**:

```
{rev, found, hash, hash_full, branches, remote_branches, tags, other_refs, reachable_from_head}
```

- Git: `for-each-ref --contains` plus `merge-base --is-ancestor <commit> HEAD`.
- Synthetic: the commit's `refs` list. When it is absent, the commit is on `repo.branch`.
  `reachable_from_head` is `None` when `repo.branch` is unknown.

**RepoInfo**:

```
{is_git, git_available, mode, reason, shallow, toplevel, prefix, head (full id or None), branch,
 detached, remote (origin URL or None), remotes {name: url}, provider, tags [newest first, capped],
 commit_count (reachable from HEAD), first_commit_date, last_commit_date, not_checked}
```

- A repo with no commits has `head: None`, `branch` from `symbolic-ref`, and `commit_count: 0`.
- Synthetic mode fills these fields from `repo` and the commit list, with `toplevel: None`.

## CLI

```
python githist.py {log|churn|blame|added-lines|tickets|info} <root> [--history FILE | --no-git] [--as-of D] [--out FILE] ...
python githist.py <root> [--history FILE] [--no-git] [--as-of D]     # legacy one-screen summary
```

Envelope, always:

```
{tool: "audit-git-history", contract: "1.0", command, root, history: {mode, reason, shallow},
 as_of, query: {parsed options}, not_checked: [...], result}
```

| Command | Extra options | `result` |
|---|---|---|
| `log` | `--since-days --last-commits --path --all-refs --merges` | `{count, commits: [Commit]}` |
| `churn` | `--since-days --last-commits --path --all-refs --follow-renames --range FILE:START-END` | `{commits_in_window, files: [FileChurn], ranges: [{file, start, end, commits, hashes}]}` |
| `blame` | `FILE --lines START-END --group` | `{file, lines: [BlameEntry], ranges: []}`, or with `--group` `{file, lines: [], ranges: [grouped]}` |
| `added-lines` | `--path --max-commits (2000) --since-days --head-only --match --include-tree` | `{commits_scanned, count, commits_with_lines: [hash_full], lines: [AddedLine]}` |
| `tickets` | `--since-days --last-commits --path --all-refs --no-merges --subject-only` | `{commits: [TicketCommit], summary}` |
| `info` | `--path PATHSPEC (repeatable) --contains REV (repeatable) --tags N` | `RepoInfo` + `paths: [{pathspec, matches: [PathRecord]}]` + `contains: [RefsRecord]` |

- Exit code is 0 whenever the envelope was produced, including mode `none`.
- An argument error exits 2.
- `--out` writes the envelope as UTF-8 JSON and prints the path.

## Synthetic history format

Only `commits[].hash`, `commits[].date` and `files[].path` are required. The first block
below is the original `audit-technical-debt` format, unchanged; the others were added in 1.0.

```json
{
  "head_date": "2026-09-01T10:00:00Z",
  "commits": [
    {"hash": "c10", "date": "2026-09-01T10:00:00Z", "author": "dev", "message": "PROJ-1 subject\n\nbody",
     "files": [{"path": "src/a.cs", "added": 40, "deleted": 3,
                "functions": ["ImportOrders"],
                "hunks": [[120, 160]]}]}
  ],
  "blame": {
    "src/a.cs": [{"lines": "1-400", "date": "2026-07-01T00:00:00Z", "author": "dev", "commit": "c3"},
                 {"lines": "14", "date": "2023-06-14T09:00:00Z", "commit": "c0"}]
  }
}
```

Optional keys added in 1.0:

```json
{
  "repo": {"branch": "main", "remote": "https://github.com/org/repo.git", "tags": ["v1.0"], "shallow": false},
  "commits": [
    {"hash": "c04", "email": "dev@example.com", "parents": ["c03"], "refs": ["refs/heads/main", "refs/tags/v1.0"],
     "files": [{"path": "src/common/Util.cs", "old_path": "src/legacy/Util.cs", "status": "R", "binary": false,
                "added_lines": [{"line": 7, "text": "// moved"}]}]}
  ]
}
```

| Key | Meaning |
|---|---|
| `head_date` | Default `as_of`. Without it, the newest commit date is used. |
| `commits[]` | Any order; sorted newest first on load. Dates are ISO-8601; no zone means UTC. |
| `message` | Full message. The subject is its first line. |
| `parents` | More than one makes it a merge, which is excluded unless `merges=True`. |
| `refs` | Full ref names containing the commit. Without it, the commit is on `repo.branch`. With `all_refs=False`, commits whose `refs` lack `refs/heads/<repo.branch>` are skipped. |
| `files[].added`, `deleted` | Numstat counts (default 0). |
| `files[].status`, `old_path` | `A`, `M`, `D` or `R`. Without a status, the first appearance is `A` and later ones `M`, so a file is never deleted. |
| `files[].functions` | Names of functions touched, used for exact function churn by consumers. |
| `files[].hunks` | `[[start, end], ...]` new-side changed ranges, used by `hunks_for_file` and `range_churn`. |
| `files[].added_lines` | `[{line, text}]` or `[[line, text]]`, the lines `added_lines()` yields. |
| `blame` | Per-file ranges `"a-b"` or `"a"`. The smallest range containing the line wins. A file without an entry falls back to the newest commit touching it (`approx: true`). |
| `repo` | Branch, remote, tags and shallow flag, used by `info()` and `refs_containing()`. |

Exporting one from a real repo you cannot run the scripts in:

```bash
git log --no-merges -M --raw --numstat --format="%x1e%H%x1f%aI%x1f%an%x1f%ae%x1f%P%x1f%B%x1d"
```

Convert that output to JSON: one commit per `\x1e` record, and one file entry per numstat line
paired with its raw line.
