# ADR and documentation drift

The discovered architecture is the truth; documents are claims. Every claim
that the code contradicts is drift. Drift matters when it misleads the person
on call at 3 a.m. or the engineer estimating a change.

## Where claims live
- `README.md`, `README.*.md`, `docs/**/*.md`, `doc/`, `wiki/` exports.
- ADRs: `adr/`, `docs/adr/`, `docs/decisions/`, `docs/architecture/decisions/`, files named `NNNN-title.md`, `ADR-nnn.md`. Formats: Nygard (Context / Decision / Status / Consequences), MADR (`## Decision Outcome`), Y-statements.
- Diagrams: Mermaid fences in Markdown, `*.puml`/`*.plantuml`, `*.drawio` (XML with `value="..."` labels), `*.svg` exported from tools (text labels inside `<text>`), C4 DSL (`workspace { model { ... } }`), `architecture.md`.
- Config-as-docs: `docker-compose.yml` comments, `ocelotconfig.json` route names, OpenAPI `info.description`.
- `CLAUDE.md`, `CONTRIBUTING.md`, onboarding docs - often the most current prose.

## How to extract claims (`scripts/doc_drift.py` does the mechanical part)
1. Component names: Mermaid node ids and labels, PlantUML `component "X"`/`[X]`/`database "X"`, drawio `value=` labels, headings and bold/backticked identifiers in prose that look like module or service names.
2. Relationship claims: Mermaid/PlantUML arrows (`A --> B`) become "A calls B"; prose like "X publishes to Y", "all writes go through Z".
3. Decision statements: ADR title, `Status`, `Decision` paragraph, date. Extract as one sentence each.
4. Normalise names (lowercase, strip non-alphanumerics, drop suffixes `.api`, `service`, `svc`, `microapi`, `worker`) before comparing to `modules.json` and `topology.json`.

## Grading drift
| Situation | Grade | Typical severity |
|---|---|---|
| Documented component does not exist in code or topology | stale | Low; Medium if it is on the documented critical path (on-call will look for it) |
| Component exists but is absent from every diagram | undocumented | Info; Low if it is a data store, queue, or external integration |
| Documented relationship direction is reversed or missing | stale | Low |
| ADR "Accepted" but the decision is not implemented (outbox, gateway auth, DB-per-tenant) | not implemented | Medium; High if the decision was a security or consistency control |
| ADR "Accepted" and implemented, then silently replaced | superseded-in-code | Low; recommend a superseding ADR |
| No ADRs, no diagram | absent | Info finding "no recorded design decisions", plus the discovered diagram becomes the first one |
| Diagram newer than the last structural commit and matching | current | none |

## Verifying an ADR claim quickly
| Claim | Check |
|---|---|
| "events go through an outbox" | table/entity named `Outbox*`, publisher reads from it; direct `IBus.Publish`/`channel.basic_publish` in request handlers means not implemented |
| "gateway enforces authentication" | gateway config has auth options per route; downstream services also `[Authorize]`; service ports not published externally |
| "database per tenant" | connection chosen per request from claim/header; no `TenantId` column filtering as the only isolation |
| "all external calls have retries" | resilience library registered on every named/typed client |
| "stateless services" | no static mutable state, no in-memory sessions, no local uploads |
| "read replicas for reports" | second connection string / read-only context used by reporting code |

## Reporting
Produce the "ADR / documentation drift" table (Source | Claim | Reality | Drift)
and one finding per drift that is Medium or above; group Low/Info drifts into one
finding "documentation does not match the code" with all locations listed.
