---
name: audit-git-history
description: Answers factual questions about a repository's git history for audits - commits in a window with per-file numstat and rename resolution, per-file and per-line-range churn, blame age per line or range, lines added per commit for scanning history for secrets, commit messages with ticket references (JIRA keys, #123, AB#123), whether a path was ever committed and later deleted, which branches or tags contain a commit, and whether a folder is a git repo at all or a shallow clone - from a real repo or a synthetic history JSON for tests, without judging the results. Use it whenever the user asks about git history, churn or change frequency, git blame or how old a line or TODO is, secrets left in old commits, files deleted from history, ticket traceability of commits, which branch contains a commit, or whether a clone is shallow, even when they do not name this skill. Also used by other audit skills (audit-technical-debt, audit-secrets-and-config, audit-soc2-controls-evidence).
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-core:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit git history

One job: answer "what does this repository's history say?" the same way for every
audit skill. It is one module, `scripts/githist.py`, used as an import or a CLI.
Consumers get identical answers for churn, blame ages, added lines, ticket references,
deleted paths and refs, whether the source is a real repo or a synthetic history file.

It records facts only. Whether a hot file is debt, a matched line is a secret, or a
ticket ratio passes a control is decided by the consumer skill that asked.

Read-only rule: only read-only git commands run (`log`, `show`, `blame`, `rev-parse`,
`rev-list`, `ls-tree`, `for-each-ref`, `merge-base`, `tag`, `config --get`). History is
never rewritten, nothing is fetched, and the working tree is never touched. Output goes
to stdout or to the `--out` path the caller chooses.

## Inputs and prerequisites

- A repository root. It may be a subfolder of a repo; paths are then relative to it.
- One history source:
  - **git**: git on PATH and the root inside a work tree. This is the default.
  - **synthetic**: `--history FILE` for fixtures, source exports, or zip uploads with no `.git`.
  - **none**: `--no-git`, or an automatic fallback when neither of the above applies.
- Python 3, standard library only.
- `audit-code-scan` installed next to this skill. Its `repo_walk.py` walks working-tree
  files for `--include-tree`, so tree lines cover the same files as every other audit.
- No stack detection is needed. History questions are language-neutral, so this skill
  never reads `audit/stack.json`.

## Workflow

1. **Check the source before trusting any number.** Run `info` first:

   ```bash
   python <skills-dir>/audit-git-history/scripts/githist.py info <repo>
   ```

   Read `history.mode`, `result.shallow` and `not_checked`. The results mean:
   - **Mode `none`:** there is no history. Every history-based answer is "not checked",
     never "zero".
   - **Shallow clone:** churn, blame ages, deleted-path and added-line answers are
     truncated at the clone depth. Report them as not checked, or ask for a full clone.
   - **Blame `boundary: true`:** the line comes from a boundary commit. In a shallow
     clone that commit stands in for everything older, so the age is a lower bound.
2. **Ask the question with the matching subcommand.** Every subcommand takes `--history FILE`,
   `--no-git`, `--as-of YYYY-MM-DD` and `--out FILE`:

   | Question | Command |
   |---|---|
   | Commits in a window, per-file numstat, renames | `log <repo> [--since-days N] [--last-commits N] [--path P] [--all-refs] [--merges]` |
   | Per-file churn, line-range churn | `churn <repo> [window] [--follow-renames] [--range FILE:START-END]` |
   | Blame age of a line or range | `blame <repo> FILE [--lines START-END] [--group]` |
   | Lines added per commit (history secret scan) | `added-lines <repo> [--path P] [--max-commits 2000] [--head-only] [--match REGEX] [--include-tree]` |
   | Ticket references in commit messages | `tickets <repo> [window] [--subject-only] [--no-merges]` |
   | Was a path ever committed or later deleted | `info <repo> --path config/.env --path ":(glob)**/.env"` |
   | Which branches or tags contain a commit | `info <repo> --contains <rev>` |

   From a consumer script, load the module by file path under a unique module name, never
   through `sys.path`. The loader snippet and every function are listed in
   `references/githist-contract.md`.
3. **Fix the reference date for reproducible runs.** Ages and windows count back from
   `--as-of`. The default is the synthetic `head_date`, or now for git.
4. **Keep scans bounded.** `added-lines` walks up to `--max-commits` commits across all
   refs by default. Pass `--match` or `--path` on large repos, and report the cap that was used.
5. **Hand the facts back without a verdict.** Copy `not_checked` into the consumer's
   Not checked list verbatim. Ticket rules and path matches are fixed patterns, not
   judgements. For example, a `#12` in a commit message is recorded even when it is not an issue link.

## Output contract

Every CLI call prints one JSON envelope:

```json
{"tool": "audit-git-history", "contract": "1.0", "command": "churn", "root": "abs path",
 "history": {"mode": "git|synthetic|none", "reason": "...", "shallow": false},
 "as_of": "2026-09-01T00:00:00Z", "query": {"since_days": 365},
 "not_checked": [{"item": "full git history", "reason": "..."}],
 "result": {"commits_in_window": 7, "files": [], "ranges": []}}
```

The `result` shape per subcommand, the Python return shapes (dates are `datetime` in
Python and ISO-8601 UTC strings in JSON), the synthetic history format, and the
stability promise are in `references/githist-contract.md`. Consumers code against that
file, not against this summary.

## Limits

- **Churn follows no renames by default.** Pre-rename commits count under the old path;
  pass `--follow-renames` to fold them into the newest name. Squash merges undercount churn.
- **Range churn maps hunks onto today's line numbers.** It is approximate for code that
  moved within the window. Synthetic range churn needs `hunks` entries.
- **Blame honours `.git-blame-ignore-revs`** when it exists at the repo top. A bulk
  reformat not listed there makes lines look young.
- **Merge commits in `added-lines`** contribute only lines new to every parent. Lines
  that arrived from a side branch are reported at their original commit, if that commit
  is inside `--max-commits`.
- **Ticket rules** match JIRA-style keys (upper case, with a small deny list such as
  UTF-8 and SHA-256), `#123`, `AB#123`, and `fixes/closes/resolves 123`. Lower-case keys
  and bare numbers are not tickets here.
- **Path questions use git pathspecs.** `.env` means the repo-root file only; use
  `:(glob)**/.env` for any depth. A rename is reported as `renamed`, not `deleted`.
- **Synthetic mode knows only what the file says.** No `status` means a file was never
  deleted; no `refs` means every commit is on the head branch.
- **Rewritten history** (filter-repo, force-push) and unfetched remote branches are
  invisible. Only local refs are read.

## Bundled files

- `scripts/githist.py`: the importable module and CLI (`log`, `churn`, `blame`,
  `added-lines`, `tickets`, `info`). It also keeps the legacy `githist.py <repo>` summary.
- `references/githist-contract.md`: function signatures, return shapes, the CLI envelope,
  the synthetic history JSON format, and the stability promise.
- `evals/files/synthetic-history.json`: a synthetic history with a rename, a deleted
  secret, ticket ids, an unmerged branch and a merge.
- `evals/files/build_sample_repo.py`: builds the equivalent real git repo, and optionally
  a shallow clone, on demand. A skill never ships a `.git` folder.
- `evals/evals.json`: realistic prompts with expectations.
