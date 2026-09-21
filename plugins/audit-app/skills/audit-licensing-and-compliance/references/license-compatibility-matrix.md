# Licence compatibility matrix

Human-readable twin of `scripts/license-policy.json` (the script is authoritative; keep
both in sync). Rows are licence categories, columns are the project's distribution
model, cells are the verdict the inventory assigns. This is an engineering triage aid,
not legal advice: every **incompatible** or **review** cell needs a decision recorded by
someone entitled to make it.

## Distribution models

| Model | Meaning | Typical projects |
|---|---|---|
| **proprietary** | Code or binaries are shipped to customers (installers, mobile apps, desktop, on-prem, a JavaScript bundle served to browsers counts as distribution of that bundle) | Mobile/desktop apps, on-prem servers, SDKs, Angular/React/Vue bundles |
| **saas** | Only run on your own servers; customers interact over the network; the frontend bundle is still distributed | Multi-tenant web products (use `saas` for the backend and treat the frontend bundle as `proprietary`) |
| **open-source** | The project itself is released under an OSI licence | Libraries, community editions |

## The matrix

| Category | Licences | proprietary | saas | open-source |
|---|---|---|---|---|
| **permissive** | MIT, ISC, BSD-2/3, Apache-2.0, 0BSD, Unlicense, CC0, Zlib, BSL-1.0, MS-PL, PSF, Artistic-2.0, OFL-1.1 (fonts), CC-BY-4.0 (content) | attribution | attribution | attribution |
| **weak copyleft** | LGPL-2.1/3.0, MPL-2.0, EPL-1.0/2.0, CDDL, CC-BY-SA | review | review | attribution |
| **strong copyleft** | GPL-2.0, GPL-3.0 (with or without -only/-or-later) | incompatible | review | review |
| **network copyleft** | AGPL-3.0, SSPL-1.0, EUPL-1.2 | incompatible | incompatible | review |
| **restricted / source-available** | CC-BY-NC, CC-BY-ND, BUSL-1.1, Elastic-2.0, Commons Clause, "Proprietary", "UNLICENSED", "SEE LICENSE IN ..." | incompatible | incompatible | incompatible |
| **unknown** | no metadata, unparsable expression, package not in local cache | unknown | unknown | unknown |

Verdict meanings and the severity the finding gets:

| Verdict | Meaning | Severity |
|---|---|---|
| attribution | Allowed; the licence text and copyright notice must ship with the product (THIRD-PARTY-NOTICES.md). Missing notices file = one Medium finding covering all of them. | - / Medium if no notices |
| review | Usually allowed when the library is used unmodified and consumed as a package; document the decision per package. | Medium |
| incompatible | Cannot ship under this model without a commercial licence, a replacement, or changing the model. | High |
| unknown | No rights granted until known; blocks sign-off. Usually a metadata gap. | Medium (confidence `likely`) |

## Why the cells are what they are

- **Apache-2.0 vs GPL-2.0**: Apache-2.0 code cannot be combined into a GPL-2.0-only work
  (patent clause conflict); irrelevant for proprietary/SaaS but matters for open-source
  projects licensed GPL-2.0.
- **LGPL in a compiled or bundled client**: LGPL allows proprietary use if the user can
  relink/replace the library. A minified Angular bundle or a statically linked mobile
  binary makes that hard; treat LGPL in *frontend bundles and mobile apps* as
  `review` leaning `incompatible`, and LGPL consumed as a NuGet/npm package on the server
  as fine.
- **MPL-2.0**: file-level copyleft; you must publish changes to MPL files only. Almost
  always fine; still record it.
- **GPL on the server (SaaS)**: the GPL's obligations trigger on distribution; running
  GPL code to serve a website is not distribution (that is exactly the loophole AGPL
  closes). `review` because teams often later ship an on-prem edition and get stuck.
- **AGPL (SaaS)**: section 13 - users interacting over a network must be offered the
  source of the modified program. Linking AGPL code into your service means your service.
  Common offenders: iText 7 (AGPL/commercial), Ghostscript, MongoDB drivers are Apache but
  the *server* is SSPL, Grafana/Loki (AGPL), MinIO (AGPL), Berkeley DB, Ghostscript.NET.
- **Dual-licensed packages** (`MIT OR Apache-2.0`): choose the most permissive; the
  script does. `X AND Y`: the most restrictive governs.
- **"UNLICENSED" / no `license` field**: under copyright law no licence means no
  permission. npm's `private: true` packages with no field are your own code; a
  third-party package with no field is `unknown` until its repo shows a LICENSE file.
- **Fonts and icons**: OFL requires shipping the licence and forbids selling the font
  alone; CC-BY requires visible attribution (About page / notices).
- **Container base images**: the image is an aggregate; using it is fine. Copying GPL
  binaries out of it into your own artefact is distribution.

## Attribution obligations by licence

| Licence | Must ship | Must also |
|---|---|---|
| MIT / ISC / BSD | copyright line + licence text | BSD-3: no endorsement using the author's name |
| Apache-2.0 | licence text + NOTICE file contents if the package has one | state changes if you modified files |
| LGPL / MPL / EPL | licence text + source (or offer) of the library itself and any changes to it | keep the library replaceable (LGPL) |
| OFL-1.1 | licence text with the font | do not sell the font by itself |
| CC-BY-4.0 | credit, licence link, indicate changes | - |

`THIRD-PARTY-NOTICES.md` generated by the script satisfies the first column when it is
actually shipped (About page, package root, container image `/licenses`).

## Recording a decision

Add the decision to the finding's remediation or a `decisions` section in the notices
file, one line per package:

```
chart-bindings 1.4.0 - LGPL-3.0 - used unmodified via npm; bundle keeps it as a separate chunk; approved by <name> on <date>.
pdf-render-agpl 2.1.0 - AGPL-3.0 - REPLACE before launch with pdf-lib (MIT); ticket INV-412.
```
