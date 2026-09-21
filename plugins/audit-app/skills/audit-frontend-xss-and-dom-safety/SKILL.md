---
name: audit-frontend-xss-and-dom-safety
description: Finds cross-site scripting (XSS) and unsafe DOM manipulation in web frontends - framework sanitizer bypasses (Angular DomSanitizer.bypassSecurityTrust*, React dangerouslySetInnerHTML, Vue v-html), direct innerHTML/outerHTML/document.write, unsafe ElementRef or ref DOM access, href/src/URL built from user input including javascript-scheme URLs, eval/new Function/setTimeout-with-string, third-party scripts without Subresource Integrity, and inline scripts that break CSP - traces each hit to its data source and labels every bypass justified or unjustified. Use this whenever the user asks about XSS, cross-site scripting, sanitization, sanitizer bypass, innerHTML, v-html, dangerouslySetInnerHTML, DOM safety, DOM-based XSS, "is this template safe", trusted types, SRI, inline scripts, frontend security, client-side security, or as part of any security audit or pre-production review that includes an Angular, React, Vue, or server-rendered web frontend - even when the user does not name this skill.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-app:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit: frontend XSS and DOM safety

Modern frameworks escape by default, so nearly every frontend XSS is a place
where someone stepped outside the framework: a sanitizer bypass, a raw DOM
write, a URL assembled by hand, a string handed to `eval`, or a script tag
loaded from a CDN with no integrity check. This skill finds those places with a
per-framework grep, traces each one to its data source, and separates the
bypasses that are justified (sanitized first, constant input, documented
reason) from the ones that are not.

Read-only rule: never edit the audited code. Write only under `audit/`
(`findings`, `reports`, `evidence`, `status`).

## Inputs and prerequisites

- Path to the repository root (a frontend project, or a full-stack repo whose
  server renders HTML - Razor, Thymeleaf, EJS, Django templates count).
- `audit/stack.json` if `audit-application` already ran; otherwise run
  `$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py`.
- Python 3 (stdlib only) for the bundled scripts.
- Skills from the `audit-core` plugin (reached via `$AUDIT_CORE_ROOT`, exported by that plugin; a sibling `skills/` layout also works): `audit-stack-detection` (stack), `audit-code-scan` (grep pass and the shared file walker `scan_html_scripts.py` imports), `audit-finding-writer` (findings.json).
- Optional: the CSP reported by `audit-security-headers-and-middleware`
  (`audit/findings/audit-security-headers-and-middleware.json`) - a strict CSP
  is a compensating control that can lower severity one step; the absence of
  one is context for the inline-script findings.

## Workflow

1. **Resolve the stack.** `python "$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py" <repo>`. Open only
   the matching `references/<stack>.md`: `angular.md`, `react.md`, `vue.md` for
   SPAs; `dotnet.md`, `java-spring.md`, `node-express.md`, `python-django.md`
   for server-rendered templates and API responses that carry HTML. A repo can
   need two files (Angular SPA plus a Razor login page). No match: use
   `$AUDIT_CORE_ROOT/skills/audit-stack-detection/references/stack-reference-template.md` as the outline and say so in scope.
2. **Automated pass.** For every stack with a pattern file:
   `python "$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py" <repo> --patterns scripts/patterns/<stack>.json --out audit/evidence/audit-frontend-xss-and-dom-safety/hits-<stack>.json --md audit/evidence/audit-frontend-xss-and-dom-safety/hits-<stack>.md`.
   Then `python scripts/scan_html_scripts.py <repo> --out audit/evidence/audit-frontend-xss-and-dom-safety/scripts.json`
   to list every `<script src>` from a foreign origin without `integrity`, every
   inline `<script>` and inline event handler, and any `javascript:` href in
   static HTML. Pattern ids map to the sink classes in
   `references/xss-sinks.md` (BYPASS, HTML, DOM, URL, EVAL, SRI, INLINE, SSR).
3. **Manual trace of the highest-risk flows.** For each hit answer: (a) where
   does the value come from - a user-editable field, an API response that
   echoes user input, a route/query parameter, `postMessage`, `localStorage`,
   or a constant in the source; (b) what happens before the sink - a real
   sanitizer (`DOMPurify.sanitize`, Angular's `sanitize(SecurityContext.HTML)`,
   `sanitize-html`, `xss`), a URL scheme check, an allow-list, or nothing;
   (c) who sees the result - only the author (self-XSS, Low) or other users and
   admins (stored XSS, High). Label every sanitizer bypass **justified** (a
   sanitizer runs on the same value immediately before, or the input is a
   constant/server-controlled trusted resource, and the reason is stated in
   code or docs) or **unjustified**. A justified bypass is still recorded, as
   an Info finding, so the next auditor does not re-open it. Beyond the hits,
   trace the flows the reference's checklist names: rich-text/comment/notes
   fields, "preview" screens, PDF/print views, notification toasts that render
   server text, markdown renderers, iframe/embed URLs, deep-link handlers.
4. **Write findings** with `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py`, id prefix `XSS`. One finding
   per root cause (a shared `SafeHtmlPipe` used in nine templates is one
   finding with nine locations). Severity via
   `audit-finding-writer/references/severity-rubric.md`: stored XSS visible to
   other users or admins is High (Critical when the app is multi-tenant and
   the payload reaches another tenant or an admin console); reflected XSS
   needing a crafted link is Medium; self-XSS and missing SRI are Low;
   justified bypasses are Info. Put the justified/unjustified label in `tags`
   and in the first words of Evidence.
5. **Produce the outputs** (paths relative to the audited repo):
   - `audit/findings/audit-frontend-xss-and-dom-safety.json`
   - `audit/reports/audit-frontend-xss-and-dom-safety.md` (skeleton below)
   - `audit/evidence/audit-frontend-xss-and-dom-safety/hits-<stack>.json|md`, `scripts.json`
   - `audit/status/audit-frontend-xss-and-dom-safety.json`:
     the status record defined in `audit-core:audit-finding-writer` (references/run-status.md)
6. **List what was not checked**: third-party widgets whose source is not in
   the repo, minified vendor bundles, mobile WebView bridges, server-rendered
   emails, and any runtime-only sink (a CMS that injects HTML) you could not
   see from source. Also list the automated pass's coverage limits from `audit-code-scan`: folders on the shared skip list (`node_modules`, `bin`, `obj`, `dist`, `build`, `.git`, `audit`, ... - see `$AUDIT_CORE_ROOT/skills/audit-code-scan/references/repo-walk-api.md`) and files over 2 MB are not read, and patterns match one line at a time. `scan_html_scripts.py`
   uses the same walker, so HTML or template files over 2 MB and files under skipped
   folders (built `dist/` output included) are not listed.

## Finding format

Write findings using `audit-core:audit-finding-writer`, with ID prefix `XSS`.
Use its canonical schema and severity rubric. Topic-specific field guidance:

- **Confidence:** confirmed | likely | false-positive

- **Impact:** Plain language. Who is affected, what they lose, how likely. One or two sentences, ending with the severity justification.
- **Remediation:** The concrete fix in this framework, with a short example. Name the file and the pattern to use.
- **Reference:** CWE-nnn, ASVS-x.y.z, OWASP-A0n:2021


JSON fields: `id`, `title`, `severity`, `confidence`, `location`, `evidence`,
`impact`, `remediation`, `references`, `tags` (sink class in lower case plus
`justified` or `unjustified` for bypasses). Full schema and prefix table:
`audit-finding-writer/references/findings-schema.md`.

## Output template - `audit/reports/audit-frontend-xss-and-dom-safety.md`

```markdown
## audit-frontend-xss-and-dom-safety findings

| Critical | High | Medium | Low | Info |
|---|---|---|---|---|
| n | n | n | n | n |

### Scope
- Stack(s): angular 19 (src/app), razor (Account.MicroAPI/Views)
- Pattern files: scripts/patterns/angular.json, scripts/patterns/dotnet.json
- Hits: NN total -> NN confirmed, NN likely, NN false-positive
- CSP in place: yes/no/unknown (from audit-security-headers-and-middleware)

### Sanitizer bypass register
| Location | API | Data source | Sanitized before? | Label | Finding |
|---|---|---|---|---|---|
| `comment.component.ts:18` | bypassSecurityTrustHtml | comment.body (user, stored) | no | unjustified | XSS-001 |
| `help.component.ts:22` | bypassSecurityTrustHtml | help article (CMS) | DOMPurify.sanitize | justified | XSS-003 (Info) |

### Other sinks
| Class | Location | Data source | Label | Finding |
|---|---|---|---|---|
| dom | `preview.component.ts:31` | nativeElement.innerHTML = product.description | confirmed | XSS-002 |

### Third-party scripts and inline code (from scan_html_scripts.py)
| File | Kind | src / snippet | SRI | Issue |
|---|---|---|---|---|
| `src/index.html` | external | https://cdn.example.com/widget.js | missing | XSS-004 |
| `src/index.html` | inline | window.dataLayer=... | n/a | blocks strict CSP |

### Findings
<one block per finding, Critical first>

### Not checked
- <item> - <reason>
```

## Examples

**Input (hit):** `src/app/comments/comment.component.ts:18: this.safeBody = this.sanitizer.bypassSecurityTrustHtml(comment.body);`

**Output:**
```markdown
### [High] XSS-001 - Comment body rendered through bypassSecurityTrustHtml without sanitization
- **Location:** `src/app/comments/comment.component.ts:18` (ngOnInit)
- **Confidence:** confirmed
- **Evidence:**

```ts
// unjustified: comment.body is typed by any user and stored; nothing sanitizes it
this.safeBody = this.sanitizer.bypassSecurityTrustHtml(comment.body);
```

- **Impact:** Any user who can post a comment can run script in every other user's browser that opens the thread, including admins - session theft and actions performed as them. Rated High (stored, reaches other users); would be Critical if admin pages render the same comments.
- **Remediation:** Bind with `[innerHTML]="comment.body"` and let Angular sanitize, or if formatting must survive run `DOMPurify.sanitize(comment.body, { ALLOWED_TAGS: [...] })` before the bypass and add a comment stating why the bypass exists.
- **Reference:** CWE-79, ASVS-5.3.3, OWASP-A03:2021
```

**Input (hit):** `src/app/help/help.component.ts:22: this.html = this.sanitizer.bypassSecurityTrustHtml(DOMPurify.sanitize(article.html));`

**Output:** an **Info** finding tagged `justified` recording that the bypass is
preceded by `DOMPurify.sanitize` on the same value, with the remediation
"keep the sanitizer call adjacent to the bypass and cover it with a unit
test"; it appears in the bypass register with Label = justified.

## Bundled files

- `references/xss-sinks.md` - sink classes, source vocabulary, the justified/unjustified rubric, SRI and inline-script rules, severity anchors.
- `references/<stack>.md` - per-framework bypass API names, sinks, safe idioms, trace checklist, false positives, tooling (`angular`, `react`, `vue`; `dotnet`, `java-spring`, `node-express`, `python-django` for server-rendered HTML). To add a stack, follow `$AUDIT_CORE_ROOT/skills/audit-stack-detection/references/stack-reference-template.md`.
- `scripts/patterns/<stack>.json` - per-framework grep pattern lists (format: `$AUDIT_CORE_ROOT/skills/audit-code-scan/references/pattern-file-format.md`).
- `scripts/scan_html_scripts.py` - lists external scripts without SRI, inline scripts/handlers, and `javascript:` URLs in HTML/template files; walks the repo with `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/repo_walk.py`.

Atomic scripts this skill calls (installed next to it, not bundled):

- `$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py` - stack detection (honours `audit/stack.json`).
- `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py` - pattern-driven automated pass.
- `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/repo_walk.py` - shared walker imported by `scan_html_scripts.py`.
- `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py` - init / add / validate / md / summary for findings.json.
- `evals/` - prompts, an Angular fixture with one unjustified bypass, one raw innerHTML write, one justified bypass, and a CDN script without SRI.
