---
name: audit-accessibility-and-i18n
description: Reviews frontend code (Angular, React, Vue, and server-rendered templates) for WCAG 2.2 AA basics - form labels, image alt text, colour contrast, keyboard navigation, focus management in dialogs and on route change, ARIA correctness, semantic HTML, skip links - and for internationalization readiness - hard-coded user-facing strings, locale-aware date/number/currency formatting, pluralization, RTL support and text-expansion tolerance - wrapping axe-core when available and reporting findings grouped by WCAG criterion with a hard-coded-string count per file and a prioritized fix list. Use it whenever the user asks about accessibility, a11y, WCAG, screen readers, keyboard support, focus traps, ARIA, alt text, colour contrast, internationalization, i18n, localization, l10n, translations, hard-coded strings, locale formatting, pluralization, RTL or Arabic/Urdu/Hebrew layouts, even when they do not name this skill.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-app:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit accessibility and i18n

Reviews the frontend for the WCAG 2.2 AA basics that block real users (labels,
alt text, keyboard, focus, contrast, ARIA, semantics) and for whether the app
can be localized without a rewrite (no hard-coded strings, locale-aware
formatting, plural rules, RTL, room for longer text). Both are reported in the
shared finding format, grouped by WCAG success criterion so the report maps to
a legal standard, with a per-file count of hard-coded strings and a fix list
ordered by user impact.

Read-only rule: never modify the audited code. Write only under `audit/`.
Running axe against a served build is allowed; it does not touch the repo.

## Inputs and prerequisites

- Repo root (defaults to `.`). Standalone runs read `audit/stack.json` if
  present, else run `python "$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py" <repo>`
  (without `--write`, so a standalone run does not create `audit/stack.json`).
- Python 3 (stdlib only). Optional: Node with `@axe-core/cli` (or `pa11y`,
  Lighthouse) and a served build for the automated checker; a screen reader
  (NVDA/VoiceOver) for the manual pass.
- Which locales are required, and whether any is RTL (`ar`, `he`, `fa`, `ur`).
  If the user does not say, infer from `assets/i18n/*.json`, `.resx`,
  `messages_*.properties`, `locale/*/LC_MESSAGES`, and state the assumption.
- Sibling skills: `audit-frontend-xss-and-dom-safety` (sanitization),
  `audit-frontend-best-practices` (build and code style),
  `audit-datetime-and-timezone` (server-side time handling; this skill covers
  only the *display* locale). Backend reference files here cover server-rendered
  templates and locale negotiation only.
- Skills from the `audit-core` plugin (reached via `$AUDIT_CORE_ROOT`, exported by that plugin; a sibling `skills/` layout also works): `audit-stack-detection` (stack detection), `audit-code-scan` (grep pass, and the shared `repo_walk.py` walker the bundled scripts import) and `audit-finding-writer` (`$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py`). A missing one stops the scripts with an error naming it.

## Workflow

1. **Resolve the stack.** `python "$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py" <repo>`; open
   `references/<primary_frontend>.md`. If the backend renders HTML (Razor,
   Thymeleaf, Django templates, EJS) or negotiates the locale, open that
   backend file too. Read `references/wcag22-aa-checklist.md` and
   `references/i18n-checklist.md` once; they are the criteria list.
2. **Automated pass.** Save under `audit/evidence/audit-accessibility-and-i18n/`:
   - `python scripts/template_scan.py <repo> --out audit/evidence/audit-accessibility-and-i18n/templates.json --md audit/evidence/audit-accessibility-and-i18n/templates.md`
     scans Angular/React/Vue templates (and plain HTML / server templates):
     inputs without an accessible label (WCAG 1.3.1 / 3.3.2 / 4.1.2), images
     without `alt` (1.1.1), dialogs without focus-trap markers (2.1.2 / 2.4.3),
     click handlers on non-interactive elements (2.1.1), icon buttons without a
     name (4.1.2), positive `tabindex` (2.4.3), missing `lang` (3.1.1),
     `outline: none` (2.4.7), and **hard-coded user-facing strings with a count
     per file**.
   - `python "$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py" <repo> --patterns scripts/patterns/<stack>.json --out audit/evidence/audit-accessibility-and-i18n/hits.json`
     for the code-side shapes: `toLocaleDateString()` without a locale,
     `toFixed`/manual currency formatting, string concatenation for plurals,
     physical CSS properties (`margin-left`) instead of logical ones, fixed
     widths on text containers, `dir="ltr"` hard-coded.
   - `python scripts/axe_runner.py --url http://localhost:4200/ --url http://localhost:4200/checkout --out audit/evidence/audit-accessibility-and-i18n/axe`
     wraps `@axe-core/cli` when installed (falls back to `pa11y`; otherwise
     prints the install command and records "not run"). Run it against the
     five most important routes of a served production build.
   Every hit is a candidate; component libraries (Material, Ionic, Headless UI)
   often supply the label or trap the focus themselves - the stack file lists
   these false positives.
3. **Manual trace of the highest-risk flows.** In this order: (a) the
   legally or commercially critical flow (checkout, login, order entry): tab
   through it with the mouse unplugged, then with a screen reader; check every
   error message is announced (3.3.1, 4.1.3); (b) every dialog/modal: focus
   moves in on open, stays in, returns to the trigger on close (2.4.3, 2.1.2);
   (c) route changes: focus/heading announced, `<title>` updated (2.4.2);
   (d) the densest data page (POS grid, dashboard): contrast of status colours
   and non-text UI (1.4.3, 1.4.11), colour-only status (1.4.1), 200% zoom and
   320 px reflow (1.4.4, 1.4.10); (e) i18n: switch to the longest locale
   (German) and an RTL locale if required - truncation, overlap, mirrored
   icons, number/date format on the same pages.
4. **Write findings** with `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py`. Prefix `A11Y`. Group one
   finding per criterion per root cause ("14 inputs across 6 forms use
   placeholder as the only label" is one finding with all locations in
   Evidence). Reference `WCAG-x.y.z` plus the level; i18n findings without a
   WCAG criterion reference `WCAG-3.1.1`/`3.1.2` where language applies, else
   an empty list with tag `i18n`. Severity per the rubric: a WCAG failure that
   blocks a legally required or revenue flow for keyboard/screen-reader users
   = High (Critical if there is no alternative path); contrast/label gaps on
   secondary pages = Medium; i18n readiness gaps = Medium when a second locale
   is planned, Low otherwise.
5. **Produce outputs**: `audit/findings/audit-accessibility-and-i18n.json`,
   `audit/reports/audit-accessibility-and-i18n.md` (template below: findings
   grouped by WCAG criterion, hard-coded string count by file, prioritized fix
   list), evidence files, and `audit/status/audit-accessibility-and-i18n.json`
   (`{"skill","status":"completed|failed|skipped","reason","started_at","finished_at"}`).
6. **List what was not checked**: axe not run (no served build), no screen
   reader pass, contrast not measured on dynamic themes, locales not exercised,
   PDF/exports, native mobile shells, etc. Also list what the automated pass did
   not read: folders skipped by the shared walker (`repo_walk.SKIP_DIRS` in `audit-code-scan`: `.git`, `node_modules`, `bin`, `obj`, `dist`, `build`, `target`, `coverage`, `.angular`, `.next`, the `audit` workspace and similar) and files over 2 MB. Vendored template folders that are not skipped (for example `wwwroot/lib`) are scanned like app code;
   discount their hits by hand.

## Finding format

Write findings using `audit-core:audit-finding-writer`, with ID prefix `A11Y`.
Use its canonical schema and severity rubric. Topic-specific field guidance:

- **Location:** `path/to/file.ext:LINE` (element or component)
- **Evidence:**

```html
<the exact markup, or the axe rule id and node selector>
```

- **Impact:** Plain language. Which users are blocked or confused, on which flow, how often.
- **Remediation:** The concrete fix in this stack, with a short example.
- **Reference:** WCAG-x.y.z (Level A/AA), axe rule id, framework doc


## Output template - `audit/reports/audit-accessibility-and-i18n.md`

````markdown
## audit-accessibility-and-i18n

**Target:** <repo> @ <commit> | **Stack:** <framework> | **Locales:** en, ar (RTL) | **Date:** <ISO>
**Automated checker:** axe-core <version> on <n> routes | not run (<reason>)

### Summary
| Critical | High | Medium | Low | Info |
|---|---|---|---|---|

### Findings by WCAG 2.2 criterion
#### 1.1.1 Non-text Content (A)
<finding blocks>
#### 1.3.1 Info and Relationships (A)
...
#### 2.1.1 Keyboard (A) / 2.1.2 No Keyboard Trap (A)
...
#### 2.4.3 Focus Order (A) / 2.4.7 Focus Visible (AA)
...
#### 4.1.2 Name, Role, Value (A)
...
#### Internationalization (no single criterion; 3.1.1 / 3.1.2 where language applies)
...

### Hard-coded strings by file
| File | Strings | Sample |
|---|---|---|
| src/app/checkout/checkout.component.html | 12 | "Confirm order", "Total", "Cancel" |
| ... | | |
**Total:** N strings in M files; i18n mechanism present: yes/no (<library>)

### Prioritized fix list
| # | Fix | Criteria | Findings | Effort | Unblocks |
|---|---|---|---|---|---|
| 1 | Add visible labels / aria-label to the 14 unlabeled inputs | 1.3.1, 3.3.2, 4.1.2 | A11Y-001 | S | screen-reader checkout |
| 2 | Trap and restore focus in the confirm dialog | 2.1.2, 2.4.3 | A11Y-003 | S | keyboard checkout |
| ... | | | | | |

### Not checked
- <item> - <reason>
````

## Examples

**Input (template_scan.py row):**
`input-no-label  src/app/checkout/checkout.component.html:14  <input formControlName="email" placeholder="Email">`

**Output:**
````markdown
### [High] A11Y-001 - Checkout email field has no accessible label
- **Location:** `src/app/checkout/checkout.component.html:14` (input[formControlName=email])
- **Confidence:** confirmed
- **Evidence:**

```html
<input formControlName="email" placeholder="Email">   <!-- no <label for>, no aria-label -->
```

- **Impact:** Screen-reader users hear "edit text" with no name and cannot tell which field this is; the placeholder disappears once they type. Checkout is the revenue path, so this blocks a class of customers from paying.
- **Remediation:** Add a visible label: `<label for="email">Email</label><input id="email" formControlName="email">`; with Angular Material use `<mat-form-field><mat-label>Email</mat-label><input matInput ...></mat-form-field>`. Keep the placeholder only as an example value.
- **Reference:** WCAG-1.3.1 (A), WCAG-3.3.2 (A), WCAG-4.1.2 (A), axe: label
````

**Input (grep hit):** `src/app/reports/report.component.ts:31: this.count + ' items'`

**Output:** `[Medium] A11Y-007 - Plural forms built by string concatenation`, Evidence lists
every concatenation site, Impact explains that Arabic has six plural forms and the
translator cannot express them, Remediation uses ICU `{count, plural, one {# item} other {# items}}`
via `@angular/localize` or ngx-translate's `TranslateMessageFormatCompiler`, Reference:
empty WCAG, tag `i18n`.

## Bundled files

- `references/angular.md`, `react.md`, `vue.md` - a11y and i18n idioms, component-library false positives, tooling per framework.
- `references/dotnet.md`, `java-spring.md`, `node-express.md`, `python-django.md` - server-rendered templates, locale negotiation, resource files; what to defer.
- `references/wcag22-aa-checklist.md` - every Level A and AA criterion with what to check and how.
- `references/i18n-checklist.md` - strings, formatting, plurals, RTL, text expansion, with tests.
- `scripts/template_scan.py` - template scanner (labels, alt, dialogs, hard-coded strings by file, and more).
- `scripts/axe_runner.py` - wraps `@axe-core/cli` / `pa11y` when installed; records "not run" otherwise.
- `scripts/patterns/{angular,react,vue,dotnet,java-spring,node-express,python-django}.json` - run by `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py`, which also reads `.scss` and `.css`.
- Atomic scripts called: `$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py`, `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py` (and `repo_walk.py`, imported by `template_scan.py`), `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py`. To add a stack, start from `$AUDIT_CORE_ROOT/skills/audit-stack-detection/references/stack-reference-template.md`.
- `evals/` - prompts and sample pages with an unlabeled input, an image without alt, a modal without a focus trap, hard-coded strings, and clean negatives.
