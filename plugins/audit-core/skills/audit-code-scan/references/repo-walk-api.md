# repo_walk.py API

Owned by `audit-code-scan`. Any audit script that reads repository files itself
imports this module instead of defining its own skip list or walker.

## Import snippet

Audit skills are installed side by side in one skills folder, so a consumer script
reaches the walker two levels up from its own `scripts/` folder. Load it by file path
under a unique module name. Do not put another skill's `scripts/` folder on `sys.path`:
that folder also holds `grep_scan.py`, and several skills ship scripts with the same
file name, so a later bare import could resolve to the wrong one.

```python
import importlib.util
import os
import sys

_SKILLS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_WALK = os.path.join(_SKILLS, "audit-code-scan", "scripts", "repo_walk.py")
try:
    _spec = importlib.util.spec_from_file_location("audit_code_scan_repo_walk", _WALK)
    repo_walk = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(repo_walk)
except (FileNotFoundError, AttributeError, ImportError):
    sys.exit("audit-code-scan must be installed next to this skill (expected " + _WALK + ")")
```

The same shape loads any atomic skill's module: `audit-sensitive-data-catalog/scripts/catalog.py`,
`audit-git-history/scripts/githist.py`, `audit-findings-rollup/scripts/findings_rollup.py`.

## Functions

| Function | Returns | Notes |
|---|---|---|
| `iter_files(root, exts=None, names=None, globs=None, skip_dirs=None, extra_skip=(), include_dirs=(), max_bytes=2_000_000, max_depth=None, skip_hidden=False, skipped=None)` | generator of absolute paths | Sorted, deterministic order. `globs` replaces the extension test when given. |
| `read_text(path, limit=None)` | str | UTF-8 with undecodable bytes ignored; `''` on error. |
| `read_lines(path)` | list of str | Newlines kept; `[]` on error. |
| `rel(root, path)` | str | Forward-slash repo-relative path, the form findings use. |
| `is_text_file(name, exts=None, names=None)` | bool | The test `iter_files` applies. |

### iter_files arguments to get right

- **`exts` alone still accepts extension-less names.**
  - **What happens.** When `exts` is given and `names` is left at its default, the
    `TEXT_NAMES` files are still yielded: `dockerfile`, `makefile`, `web.config`,
    `jenkinsfile` and `procfile`.
  - **To read only the given extensions,** pass `names=frozenset()`. To add specific names,
    pass a set such as `names={"dockerfile"}`.
  - **Why the default stays.** Current callers pass only `exts` and would silently lose those
    files, for example audit-secrets-and-config's `config_key_inventory.py`, whose
    environment-read pattern matches `$VAR` lines in Dockerfiles, and audit-client-auth-and-storage's
    bundle scan, which reads a deployed `web.config`. The `repo_walk.py --ext` CLI counts them too.
- **`max_bytes=None` disables the size cap.** This is supported. Use it for consumers that
  must read large files, such as bundle reports, EF model snapshots and evidence collectors,
  and say so in the consumer's Not checked or Limits text.
- **`skip_hidden=True`** also skips every folder whose name starts with `.`, for example
  `.github`, `.vscode` or `.husky`, except names passed in `include_dirs`. Dot-files are still
  read. The default `False` keeps today's walk, which reads dot folders not in `SKIP_DIRS`.
  List the hidden folders you skipped under Not checked.
- **`skipped=[]`** collects `(abs_path, reason)` for every file that passed the name test but
  was not yielded:
  - reason `too large: <n> bytes > max_bytes <m>`;
  - reason `unreadable: <OSError text>` when its size cannot be read.

  Only size-checked files are reported, so nothing is collected with `max_bytes=None`. Skipped
  folders and name mismatches are not reported. With the default `None` nothing is collected,
  and the walk is unchanged. List the oversized files under Not checked.

### CLI

```bash
python repo_walk.py <repo_root> [--ext .cs --ext .ts] [--extra-skip NAME] [--include-dir NAME]
                    [--count] [--skip-hidden] [--show-skipped]
```

Prints one repo-relative path per line, or the count with `--count`. `--show-skipped` then
prints `skipped: <path> (<reason>)` for every file left out by size or a read error.

## Constants

- `SKIP_DIRS`: `.git`, `node_modules`, `bin`, `obj`, `dist`, `build`, `target`,
  `.venv`, `venv`, `__pycache__`, `.idea`, `.vs`, `coverage`, `.angular`, `.next`,
  `.nuxt`, `.output`, `.gradle`, `.tox`, `.terraform`, `audit`.
- `TEXT_EXT`: source, config, template, IaC and docs extensions. Pass `exts` to narrow it.
- `TEXT_NAMES`: `dockerfile`, `makefile`, `web.config`, `jenkinsfile`, `procfile`.
- `MAX_BYTES`: 2,000,000.

## When a consumer may change the defaults

- **`extra_skip`:** when the topic explicitly excludes a folder. For example, the
  technical-debt duplicate finder skips `migrations` because generated code is not debt.
- **`include_dirs`:** when the topic needs a folder the defaults hide. For example, the
  frontend best-practices bundle report reads `dist`.
- **`skip_dirs` replacement:** never, unless the consumer documents why in its SKILL.md.
- **`packages` is deliberately not skipped:** it is a common JavaScript monorepo
  folder. `audit-stack-detection` skips it for NuGet reasons only.

Any change a consumer makes must appear in its "Not checked" list, so a reader
knows which folders the numbers exclude.

## Migrating a script from a copied skip list

A consumer that replaces its own walker with `repo_walk` gets these behaviour changes.
Check each against the consumer's fixtures and record the ones that matter under "Not checked":

- **`packages/` is read.** Most copied lists skipped it. JavaScript monorepo workspaces
  are now scanned, and so is a legacy NuGet `packages/` folder. `audit-stack-detection`
  still skips `packages/` during detection only, because NuGet restores there.
- **More folders are skipped:** `.nuxt`, `.output`, `.gradle`, `.tox`, `.terraform`.
- **Files over 2 MB are skipped** unless the consumer passes `max_bytes=None`, as a
  bundle-size report reading build output should.
- **Order is sorted and repeatable**, so hit order in outputs can change while the set stays equal.
- **Extension matching is case-insensitive**, so `README.MD` or `Startup.CS` are now read.
- **More file types are read by default:** `.scss`, `.css`, `.htm`, `.mjs`, `.cjs`, `.bicep`,
  `.prisma`, plus `Jenkinsfile` and `Procfile`. A grep pass with patterns that match styles or
  templates can gain hits; pass `exts` to narrow the set.
- **No "stop at this folder" option.** `iter_files` either skips a folder name everywhere or
  reads it everywhere. A script that must read one specific nested folder inside an otherwise
  skipped tree, such as `site-packages` under `.venv`, keeps a small targeted walk of its own for
  that folder and documents why.
- **Build output is skipped** (`dist`, `build`, `.next`, `.output`). A consumer that must
  read it passes `include_dirs`, for example `include_dirs=("dist", "build")`.
