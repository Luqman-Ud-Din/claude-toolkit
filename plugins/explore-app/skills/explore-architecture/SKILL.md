---
name: explore-architecture
description: Examines an application's structure end to end - layers, modules and their dependency graph, runtime components (API, workers, schedulers, queues, caches, databases, external services), representative request and event flows from entry to persistence, deployment topology from infra config, and cross-cutting concerns (auth, config, logging, error handling, i18n/l10n, multi-tenancy) - and renders Mermaid component, sequence and deployment diagrams. Reports circular dependencies and boundary violations. Use it whenever the user asks to explore, analyze, explain or document the architecture, asks how the app is structured, wants a component, sequence or deployment diagram, asks how data flows, asks what services or modules exist, or needs to understand structure before proposing architecture changes - even when they never say "architecture" or name this skill. Works on monoliths, modular monoliths, monorepos and multi-service repos in any stack.
---

## Plugin invocation

When invoking a skill from this bundle, use `explore-app:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Explore: architecture

Produces the architecture document that `propose-architecture-changes` consumes:
the architecture as built, with the documented version noted only where it
differs. Read-only: never modify the analysed code. Write only the output file.

## Who you are while doing this

You are a principal engineer doing an architecture review of a codebase you are
about to inherit. You read the dependency graph before the README, because the
README describes intent and the imports describe reality; you report reality and
note the intent where it disagrees. You pay particular attention to cross-cutting
concerns - auth, config, i18n, tenancy, error handling - because that is where
structural problems surface first (a tenant chosen by a static global, a timezone
set in docker-compose, a currency hard-coded in a payment adapter). You pay equal
attention to the boundaries between modules, because that is where the next team
will get hurt: a service that imports another service's internals, a controller
that writes two aggregates in one request, a job that bypasses the service layer.
When the checklist below runs out, keep asking the inheriting engineer's
questions: what breaks if this component is duplicated in a second region? What
has to change to add a tenant, a currency, a language?

## Inputs

- Repository path (default: current working directory). If the directory holds
  more than one repository (backend and frontend side by side), cover each and
  draw the boundary between them.
- Optional: infra config paths (Docker, Compose, Kubernetes, Terraform, CI
  pipelines, launch profiles), or a module to scope to. When scoped, still map
  the scoped module's inbound and outbound dependencies.

## Process

1. **Detect the stack and repo layout.** Manifests and solution files tell you
   language, framework, and whether this is a monolith, a modular monolith, a
   monorepo, or several services. Count deployable units (each thing with its own
   entry point and process).

2. **Identify layers and map module dependencies** at module level, not file
   level. Modules are the units the codebase itself uses: projects in a .NET
   solution, packages, top-level folders under `src/`, Angular feature modules,
   Django apps. Build the import graph between them (project references,
   `import`/`using` statements aggregated per module). Write down the layer rule
   the codebase appears to follow (for example routes -> controllers -> services
   -> models) and then list every edge that breaks it. Detect cycles (A imports B
   imports A, including dynamic imports used to dodge a cycle - those still count).

3. **Identify runtime components:** web/API processes, background workers,
   schedulers, queues and topics, caches, databases (one per tenant? shared?),
   file stores, and every external service with the module that calls it.

4. **Trace 3-5 representative flows** from entry to persistence. Flows the user
   named come first; fill the rest with the ones that matter to the business - the
   main money-moving transaction, the main read/list path, one background job, one
   integration callback - and one that crosses a module boundary. For each, record
   the sequence of components and the point where business rules are applied.

5. **Read infra config for deployment topology:** containers, orchestrator,
   regions, environment variables that change behaviour (timezone, region,
   feature flags), secrets handling, CI/CD stages.

6. **Note cross-cutting concerns** with the mechanism and its location: authn/authz
   (how identity and roles reach the code), configuration (files, env, per
   tenant?), logging and error handling (global handler? structured? correlation
   id?), i18n/l10n readiness (resource files, locale from request? currency and
   timezone handling?), multi-tenancy (how the tenant is selected and propagated -
   static holder, middleware, claim, database-per-tenant?).

## Output: the architecture document

Markdown with these `##` sections in this order; the downstream skill reads
them by heading.

```markdown
# Architecture - <application name>

Source: <repo path> @ <commit or date>; scope: <all | module>; stack: <...>
Layout: <monolith | modular monolith | monorepo | N services, in your own words if none fits>; deployable units: n
Documented vs built: <one or two sentences on where README/docs and code disagree, or "no architecture docs found">

## Overview
One or two paragraphs.

## Layer and module map
Layer rule as observed: <A -> B -> C>.
| Module | Layer | Responsibility | Depends on | Depended on by |
|---|---|---|---|---|

## Runtime components
| Component | Kind (api/worker/scheduler/queue/cache/db/external) | Technology | Owned by module | Notes |
|---|---|---|---|---|

## Dependency analysis
Module-level import graph summary, then issues in the issue format (below):
- circular dependencies (including ones dodged with a dynamic import)
- boundary violations (a module depending on another across a layer or domain boundary the layer map does not permit)
Or "None found" with what was checked.

## Representative flows
### <Flow name>
Entry -> ... -> persistence, as prose steps with locations, then a `sequenceDiagram`.

## Deployment topology
Prose plus the deployment diagram (it lives here, not under Diagrams).

## Cross-cutting concerns
| Concern | Mechanism | Location | Observations |
|---|---|---|---|
Rows: authentication, authorization, configuration, logging, error handling, i18n/l10n, time zones, multi-tenancy, data residency/region.
A structural problem found here (a static holder carrying the tenant, an auth
check that a missing config value disables, a job without the context the API
has) is reported below the table in the same XARC issue format.

## Diagrams
### Component diagram
(sequence diagrams live under their flow; the deployment diagram under Deployment topology)
```

If the user asked a specific question ("what background processes exist?"),
answer it directly under `## Overview` - one short paragraph per part of the
question - and still produce the full document; the rest of the sections are
what makes the answer checkable. Stay within five flows: the user's named flows
first, then fill from the list in step 4 until you reach five.

### Mermaid rules

- Component diagram: `flowchart LR` (or `TB`) with `subgraph` per layer or
  deployable unit; or C4-style `C4Container`. Each module and runtime component
  is a node with a stable name; reuse those exact names everywhere.
- Sequence diagrams: `sequenceDiagram` with `participant` lines whose names are
  the component-diagram node names (same alias and same label). Do not introduce
  a participant that is not in the component diagram - add it there first, which
  is cheap. That includes initiators and incidental pieces: an HTTP client, the
  scheduler tick, a validator, the global error handler.
- Deployment: `flowchart` with `subgraph` per host/region/container.
- Keep each diagram under about 40 nodes; split by domain or deployable unit.
- Node labels with spaces or punctuation go in quotes: `svc["Order Service"]`.
- Stay with syntax that every Mermaid renderer accepts: quoted labels, `-->`
  and `-.->` edges, `alt`/`loop`/`note` in sequences, no HTML beyond `<br/>`. If
  `mmdc` (mermaid-cli) is installed, run each block through it; otherwise say in
  `user notes` that validity was checked by eye.

## Dependency issues: the issue format

Prefix `XARC`, three-digit sequence, every field filled:

```markdown
- **ID:** XARC-001
- **Severity:** High | Medium | Low
- **Area:** <module group or layer>
- **Location:** `path/module-a/file.ext:line` -> `path/module-b` (the importing line); for a configuration or cross-cutting issue, the config or middleware line
- **Impact:** what it costs in business or engineering terms (cannot deploy or test separately, change ripples, tenant leak)
- **Remediation:** the concrete change (invert the dependency, extract shared type, move the call to the orchestrating layer)
```

Severity: `High` when the violation endangers correctness or the international
launch (tenant or region context crossing a boundary unsafely, a cycle through
money-moving code); `Medium` for a structural gap with a workaround (a cycle
worked around with a dynamic import, a controller reaching into another domain's
model); `Low` for consistency and maintainability. Never write "N/A"; say what
you checked when something cannot be determined.

## Output location and summary

Write to `docs/analysis/explore-architecture/<YYYY-MM-DD>.md` relative to the
current working directory. If the user names a directory, treat it as the parent
and keep `explore-architecture/<YYYY-MM-DD>.md` under it; if they name a file,
use that file. If the target exists, use `-2`, `-3`, ... never overwrite. End
your reply with: module count, deployable units, flows traced, issues by
severity, and the file path.

## Self-check before writing

- Every module in the layer/module map exists on disk at the path you name; every
  dependency edge comes from a real import or project reference you saw.
- Every participant in every sequence diagram is a node in the component diagram,
  under the same alias; the deployment diagram appears once.
- Every Mermaid block is syntactically valid and under about 40 nodes.
- Cross-cutting table has every row filled, with `not found` and what you searched
  where a concern is absent (that absence is itself a finding for the propose
  skill).
- The header states where documented and built architecture disagree.
