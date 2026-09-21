---
name: audit-code-scan
description: Runs the automated grep pass of an audit - walks a repository's source, config and template files with one shared skip list (node_modules, bin, obj, dist, build, .git, the audit workspace) and applies a stack-specific pattern file of regexes, emitting candidate hits with file, line, snippet, severity hint and CWE reference for manual tracing. Owns the pattern-file format and the shared file walker every audit-* script imports. Use it whenever an audit skill needs its automated pass, when the user asks to grep or scan a codebase for dangerous APIs or risky patterns, wants to write or debug an audit pattern file, asks why a file was or was not scanned, or wants to add a pattern to an audit - even when the user does not name this skill.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-core:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit code scan

One job: turn "search this repo for these patterns" into a deterministic list of
candidate hits, reading exactly the same files for every audit skill.

It deliberately knows nothing about any audit topic. Which patterns matter, and
whether a hit is a real finding, belong to the consumer skill that owns the
pattern file. A hit is a candidate until that skill traces it.

Read-only rule: the audited code is never modified. Output goes where the caller
points `--out` and `--md`, normally under `audit/evidence/<consumer-skill>/`.

## Inputs and prerequisites

- A repository root.
- One or more pattern files, normally `<consumer-skill>/scripts/patterns/<stack-id>.json`,
  chosen from the stack ids in `audit/stack.json` (see `audit-stack-detection`).
- Python 3, standard library only.

## Workflow

1. **Pick pattern files.** Use one file per detected stack id. A consumer may pass
   several `--patterns` flags, for example a stack file plus a `containers.json`.
2. **Run the scan** from the consumer skill's directory:

   ```bash
   python ../audit-code-scan/scripts/grep_scan.py <repo> \
     --patterns scripts/patterns/<stack-id>.json \
     --out audit/evidence/<consumer-skill>/hits.json \
     --md  audit/evidence/<consumer-skill>/hits.md
   ```

   Add `--extra-skip migrations` to ignore a folder the defaults read, or
   `--include-dir build` to read one the defaults skip, for example a Gradle
   `build.gradle` project whose sources sit under `build/`.
3. **Check coverage before trusting zero hits.** A pattern with count 0 means
   either "absent" or "not scanned". Confirm with
   `python ../audit-code-scan/scripts/repo_walk.py <repo> --ext .cs --count` that the
   relevant files were actually read. Some checks, like missing middleware, are
   proven by absence; say so explicitly in the consumer's findings.
4. **Hand the hits back unreviewed.** Every hit carries `status: unreviewed`. The
   consumer skill traces each one and records it as confirmed, likely, or
   false-positive in its own findings.
5. **Report what was not scanned:** skipped folders that might hold source, files over
   2 MB (`repo_walk.py <repo> --show-skipped` lists them), extensions outside the text list,
   and the line-based limit below.

## Limits the consumer must state

- **Line-based matching.** A pattern cannot span lines. A call split over two lines,
  like an annotation above a method, needs a manual trace or a consumer-specific script.
- **No parsing.** Comments and strings match like code.
- **Hit cap.** Each pattern stops at 500 hits by default, so raise
  `--max-hits-per-pattern` on large repos and report when a cap was reached.

## Shared walker for other scripts

Consumer scripts that walk files themselves must import `repo_walk.py` rather
than defining their own skip list, so all audit output describes the same files.
The import snippet, the function signatures, and when a consumer may pass
`extra_skip` or `include_dirs` are in `references/repo-walk-api.md`.

## Output

`hits.json`:

```json
{
  "root": "absolute path",
  "pattern_files": ["scripts/patterns/dotnet.json"],
  "counts": {"RAW-SQL-CONCAT": 2},
  "hits": [
    {"pattern_id": "RAW-SQL-CONCAT", "severity_hint": "High", "description": "...",
     "reference": "CWE-89", "file": "src/Repo.cs", "line": 41, "snippet": "...", "status": "unreviewed"}
  ]
}
```

`hits.md` is the same list as a Markdown table. The console gets a count summary.

## Bundled files

- `scripts/grep_scan.py` - the pattern runner.
- `scripts/repo_walk.py` - the shared walker, also a CLI listing what would be read.
- `references/pattern-file-format.md` - pattern schema, regex rules, naming, examples.
- `references/repo-walk-api.md` - import snippet and API for consumer scripts.
- `evals/` - a sample repo with planted hits, a skipped dependency folder, and a pattern file.
