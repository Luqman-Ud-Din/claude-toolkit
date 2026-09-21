---
name: audit-stack-detection
description: Detects which technology stacks a repository uses - .NET/C#, Java/Spring, Node/Express/NestJS, Python/Django/Flask/FastAPI, Angular, React/Next, Vue/Nuxt, and containers - from package manifests and project files, and writes the shared audit/stack.json that every audit-* skill reads so the stack is detected once per audit. Use it whenever the user asks what stack, language, or framework a repo uses, which references an audit should load, how to add support for a new stack to the audit skills, or when any audit-* skill needs to resolve the stack before its automated pass - even when the user does not name this skill.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-core:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit stack detection

One job: answer "which stacks does this repository use, and where" and record the
answer in `audit/stack.json`. Every other audit skill loads only the reference file
that matches this answer, so it must be computed once and shared, not re-guessed
per skill.

Read-only rule: the audited code is never modified. The only write is
`audit/stack.json`, and only when `--write` is passed.

## Inputs and prerequisites

- A repository root on disk.
- Python 3, standard library only.

## Workflow

1. **Reuse an existing answer.** If `audit/stack.json` exists, the script prints it
   unchanged. `audit-application` writes it during setup, after also asking the
   user whether the app is multi-tenant, so a child skill must not overwrite it.
   Pass `--force` only when the user asks to re-detect.
2. **Detect.** Run from the audited repository root:

   ```bash
   python <skills-dir>/audit-stack-detection/scripts/detect_stack.py <repo> [--write] [--force]
   ```

   `<skills-dir>` is the `skills/` folder of the `audit-core` plugin. From another
   plugin's skill the path is `$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py`
   (the variable is exported by audit-core's SessionStart hook); from a sibling skill
   inside audit-core it is `../audit-stack-detection/scripts/detect_stack.py`.
3. **Sanity-check the result** against what you can see. Detection is marker-based,
   so confirm three things before an audit depends on it:
   - Every `roots` entry is a real sub-project, not a sample or test fixture folder.
   - A monorepo with several backends lists all of them; `primary_backend` is only the first.
   - Next.js and Nuxt apps carry server code that is detected as `react`/`vue` only.
     Say so, and tell the caller to treat that repo as having a backend too.
4. **Hand the answer back.** Report each stack id, its evidence files, and the
   reference file name a consumer should open (`references/<id>.md`). `containers`
   has no reference file; infra skills handle it.
5. **Say what was not detected.** Stacks outside the supported list produce no entry
   and a warning. Tell the caller to follow the stack reference template to add one.

## stack.json contract

The full contract, the supported ids, and how consumers use it are in
`references/stack-json-contract.md`. In short:

```json
{
  "detected_at": "ISO-8601",
  "root": "absolute path",
  "stacks": [{"id": "dotnet", "reference": "dotnet.md", "evidence": ["Api/Api.csproj"], "roots": ["Api"]}],
  "primary_backend": "dotnet",
  "primary_frontend": "angular",
  "multi_tenant": null
}
```

`multi_tenant` stays `null` here; only `audit-application` sets it, after asking the user.

## Adding a new stack

1. Add the marker logic to `scripts/detect_stack.py` and a new id to the contract reference.
2. For each consumer skill that should support it, copy
   `references/stack-reference-template.md` to `<consumer>/references/<new-id>.md`
   and fill in every section for that skill's topic.
3. Where the consumer has a grep pass, add `<consumer>/scripts/patterns/<new-id>.json`
   in the format owned by `audit-code-scan`.

## Output

- Console: the stack.json document.
- File: `audit/stack.json` when `--write` is passed.
- A warning on stderr when no known stack marker is found.

## Bundled files

- `scripts/detect_stack.py` - detection; honours an existing `audit/stack.json`.
- `references/stack-json-contract.md` - schema, ids, consumer rules.
- `references/stack-reference-template.md` - outline every consumer stack reference follows.
- `evals/` - a polyglot sample repo, a repo with an existing stack.json, and an empty repo.
