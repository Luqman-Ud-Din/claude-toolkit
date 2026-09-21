---
name: audit-endpoint-inventory
description: Enumerates every HTTP endpoint, websocket, server action, client route and background job in a repo (ASP.NET, Spring, Express, NestJS, Fastify, Django, DRF, Flask, FastAPI, Next.js, Nuxt and Remix server handlers, Angular, React, Vue, Hangfire, @Scheduled, Celery, BullMQ, cron) and records facts per endpoint with a stable id - path, handler, auth and roles, ownership check, parameters incl. tenant and user ids, validation, response type, pagination, sensitive response fields, error shape, versioning, sequential outbound calls - into endpoints.json, endpoints.md and a probe-ready projection. Judges nothing. Use it whenever the user asks to list or inventory endpoints, routes, APIs or jobs, asks which endpoints are anonymous, paginated or take a tenant id, or needs input for an authz, tenant or load-test probe, even without naming this skill. Also used by audit-authz-and-access-control, audit-api-contract, audit-performance-and-scalability, audit-orm-query-and-data-access and audit-multi-tenant-isolation.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-core:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit endpoint inventory

One job: answer "what can be called in this repository, and what does the source say
about each entry point". The answer goes into `endpoints.json`, a record per endpoint
with a stable id. Five audit skills used to extract endpoints separately, and their
tables disagreed. This skill extracts them once, so every consumer reads the same list.

The skill records facts. It never decides that a fact is a finding. "No auth declared",
"no ownership check" and "unpaginated collection" are facts with evidence lines. Whether
one of them is a vulnerability, a contract gap or a performance risk is the consumer's
call, because only the consumer knows its topic.

Read-only rule: the audited code is never modified. The only writes are the three output
files, by default under `<repo>/audit/evidence/audit-endpoint-inventory/`.

## Inputs and prerequisites

- A repository root on disk.
- Python 3, standard library only.
- `audit-code-scan` installed next to this skill. Its `repo_walk.py` decides which files
  are read, so this inventory covers the same files as every other audit script.
- `audit-stack-detection` installed next to this skill. It is used only when
  `audit/stack.json` is absent.

Requires `audit-sensitive-data-catalog` installed next to this skill; the extractor
loads `../audit-sensitive-data-catalog/scripts/catalog.py` by path.

## Workflow

1. **Resolve the stack.** The script reads `audit/stack.json` when it exists. Otherwise
   it calls `../audit-stack-detection/scripts/detect_stack.py` without writing, so a
   standalone run leaves no state behind for the orchestrator to trust. Each extractor
   reads only the files under its stack's `roots`. That keeps Angular `.ts` files out of
   the Express extractor. Pass `--stack <id>` (repeatable) only when detection is wrong,
   and say that you did.
   Next.js and Remix handlers are read under the `react` roots and Nuxt server routes under
   the `vue` roots, because audit-stack-detection reports those frameworks as react and vue.
2. **Run the inventory** from this skill's directory:

   ```bash
   python scripts/inventory_endpoints.py <repo>
   # optional: --out-dir DIR | --out F --md F --probe F | --stack ID | --print
   ```

   The console shows a count summary. Consumers import it as a module instead:
   `inventory_endpoints.build_inventory(root)`, `probe_projection(doc)` and
   `render_markdown(doc)`.
3. **Sanity-check coverage before anyone trusts the list.**
   - `counts` per kind looks plausible for the repo, and `warnings` is empty.
   - Every stack in `stacks` produced records. If a backend produced none, check its
     `roots` in `audit/stack.json` and list the stack under "Not checked".
   - Spot-check three records against the source: path, auth source and handler line.
4. **Hand the files to the consumer unjudged.** Point consumers at
   `endpoints.json` for facts and `endpoints.probe.json` for probe input. Do not add
   severities, and do not describe records as vulnerable or broken.
5. **State the limits** below whenever the inventory feeds a report, so a reader knows
   what "not seen" can mean.

## Output contract

The full schema, field meanings, enum values and stability promise are in
`references/endpoint-inventory-contract.md`. In short:

```json
{"schema_version": "1.0", "root": "...", "stacks": ["dotnet"], "stack_source": "audit/stack.json",
 "counts": {"total": 14, "http": 12, "websocket": 0, "job": 1, "client-route": 1, "server-action": 0, "middleware": 0},
 "error_shapes": {"by_file": {}, "distinct": [], "majority": null},
 "endpoints": [{
   "id": "ep-3f9c2a1b0d", "kind": "http", "stack": "dotnet", "framework": "aspnet-controller",
   "method": "GET", "path": "/api/orders/{id}", "path_raw": "/api/orders/{id:int}",
   "file": "Controllers/OrdersController.cs", "line": 24, "handler_line": 25, "symbol": "OrdersController.Get",
   "auth": {"required": "yes", "source": "class attribute", "anonymous_marker": null, "roles": [], "policies": [], "evidence": [...]},
   "ownership": {"check": "no", "evidence": [], "identity_refs": [], "owner_key_refs": []},
   "params": [{"name": "id", "in": "route", "type": "int", "id_like": true, "identifier": "resource", "source_type": null}],
   "id_params": {"id": "order"},
   "request": {"types": [], "has_body": false, "body_type": null, "body_type_named_as_dto": null},
   "validation": {"status": "n/a", "evidence": []},
   "response": {"type": "IActionResult", "returns_collection": "no", "pagination": {"status": "n/a", "evidence": []},
                "sensitive_fields": [], "returns_entity_like": false, "projection": false},
   "errors": {"shapes_in_file": [], "consistent_with_majority": "unknown"},
   "versioned": {"status": "no", "evidence": null},
   "outbound": {"calls": [], "sequential": false, "sequential_evidence": []},
   "data_access": {"db_call_count": 1, "materializing_calls": [], "paging_seen": false, "inline_background_work": false},
   "operation": "read", "job": null, "route_location": {"file": "...", "line": 24}, "notes": []}]}
```

`endpoints.probe.json` has one row per HTTP record. Each row carries `method`, `path`,
`route`, `auth_required`, `roles`, `ownership_check` (Y/N/-/?), `id_params`,
`operation`, `kind` (read/write) and `weight`. `authz_probe.py`, `tenant_probe.py` and
`loadtest_plan.py` read it as it is. Tamper bodies and real ids stay a probe decision,
so the projection never invents them.

Server actions (`kind: server-action`) have no URL, and middleware (`kind: middleware`)
answers no route of its own, so both are in `endpoints.json` and `endpoints.md` but never
in `endpoints.probe.json`.

## Limits

- **Regex over source text, not a compiler.** Routes built at runtime are not seen:
  string concatenation, loops over route tables, reflection, attribute routing
  conventions without `[Http*]`, and routers mounted through factories. Base controllers
  are followed through `: Base` inheritance only within the repository.
- **Auth is what source declares.** Gateway rules, reverse-proxy auth, middleware
  registered in another repository and custom filters with unrecognised names show as
  `required: no, source: none` or `unknown`. Ocelot/API gateway configuration is not read.
- **Ownership is lexical.** `yes` means the handler references caller identity. It does
  not prove the reference filters the query. `unknown` means only owner or tenant key
  names appear. Checks inside services beyond one call hop are not seen.
- **One call hop.** Outbound calls and paging are followed into one callee, matched by
  receiver name to a class, for example `orders.create` to `OrdersService.create`.
  Deeper chains, dependency-injected interfaces with different names, and base-class
  helpers are not.
- **Sensitive fields come from `audit-sensitive-data-catalog`.** Only its credential and
  secret categories count, so a password hash or API key on a response type is recorded
  while personal data such as an email is left to the privacy skills. A token-issuing
  endpoint (login, refresh) reports its token field too: that is a fact, and consumers
  decide it is expected. `sensitive_fields_source` names the source in every output.
- **Job identity context** is searched in the resolved job method body. When the target
  cannot be resolved, a window after the registration is searched instead. Comments are
  ignored.
- **Meta-frameworks are read by file convention.** Next.js App Router `route.ts` handlers,
  Pages Router `pages/api` routes, server actions and `middleware.ts`; Remix and React Router
  framework-mode `app/routes/**` loaders and actions (flat-routes naming); Nuxt `server/api`,
  `server/routes` and `server/middleware`. A `pages/api` handler or Remix action is split per
  method only for `if (req.method === 'X')`, `switch (req.method)`, `!==` guards and
  `[...].includes(req.method)`. Middleware is not matched against its matcher or path
  conditions: a handler with no auth of its own, in a project whose middleware has auth
  evidence, is `required: unknown` with source `next middleware (...)` or
  `server middleware (...)`. Catch-all segments (`{slug*}`) are params but not `id_params`.
  An App Router handler that the node-express extractor already recorded keeps that record.
  Not covered: SvelteKit (`+server.ts`, form actions), React Router `app/routes.ts` routes
  other than `flatRoutes()` (the path falls back to the file name, with a note), Remix
  `clientLoader`/`clientAction`, Next.js server components and `getServerSideProps`, Nitro
  scheduled tasks, and custom `pageExtensions`, `appDirectory` or Nuxt `serverDir` settings.
- **Not read:** files over 2 MB, folders skipped by `repo_walk` (`bin`, `obj`,
  `node_modules`, `dist`, `build`, `target`, `audit`...), test-named files, `.vue`
  single-file components (routes are read from router `.ts/.js` files), crontab files,
  Go, Ruby, PHP and Rust. Next.js, Nuxt and Remix pages are not client routes here.

## Bundled files

- `scripts/inventory_endpoints.py` - CLI and module: stack resolution, file context, error
  shapes, operation rule, ids, the three outputs.
- `scripts/ep_backends.py` - dotnet, java-spring, node-express and python-django extractors.
- `scripts/ep_clients_jobs.py` - Angular/React/Vue client routes and background-job extractors.
- `scripts/ep_metaframeworks.py` - Next.js (route handlers, API routes, server actions, middleware),
  Remix / React Router framework-mode and Nuxt server handler extractors, run on react and vue roots.
- `scripts/ep_common.py` - shared helpers and per-record facts, including the catalog-backed
  sensitive-field check.
- `references/endpoint-inventory-contract.md` - schema, enum values, probe projection,
  stability promise.
- `evals/` - a multi-stack fixture (.NET controller and minimal API, Express, Django,
  Angular, Hangfire) and a meta-framework fixture (Next.js, Nuxt, Remix); the planted
  facts each one carries are asserted in `evals/evals.json`.
