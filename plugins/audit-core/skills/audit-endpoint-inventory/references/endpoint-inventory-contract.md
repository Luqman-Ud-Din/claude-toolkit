# Endpoint inventory contract

Owned by `audit-endpoint-inventory`. Consumers code against this file, not against the
script internals.

## Files

All three are written by `scripts/inventory_endpoints.py`. The default folder is
`<repo>/audit/evidence/audit-endpoint-inventory/`.

| File | What it holds |
|---|---|
| `endpoints.json` | The full inventory: one record per endpoint, websocket, server action, middleware, job and client route. |
| `endpoints.md` | The same facts as Markdown tables: HTTP and websocket, jobs, client routes, plus server actions and middleware when the repo has any. |
| `endpoints.probe.json` | The probe-ready projection. It has HTTP records only. |

## Stability promise

- `schema_version` is `"1.0"`. Within 1.x, keys are only ever added. No key is removed or
  renamed, and no enum value changes meaning.
- Every record carries every key listed below, even when a key does not apply to it.
  Such keys keep their default value. Consumers never need `.get()` for contract keys.
- A breaking change bumps the major version and is announced in this file's changelog.
- `id` is stable across runs while `kind`, `method`, `path`, `file` and `symbol` stay the
  same. It survives line moves. It changes when the route, the handler name or the file
  changes.
- Additive within 1.0: the `kind` values `server-action` and `middleware`, the matching
  `counts` keys, the frameworks `nextjs-pages-api`, `nextjs-server-action`,
  `nextjs-middleware`, `remix-route`, `nuxt-server-route` and `nuxt-server-middleware`, and
  the auth sources `handler call`, `handler wrapper`, `handler hook`, `next middleware (...)`
  and `server middleware (...)`. No existing record, id, key or enum value changed meaning.
  A consumer that filters on `kind == "http"`, or reads the probe file, gets the same rows
  as before plus meta-framework HTTP handlers.

## Top level of endpoints.json

| Key | Type | Meaning |
|---|---|---|
| `schema_version` | string | `"1.0"` |
| `generated_at` | ISO-8601 | When the run happened. |
| `root` | string | Absolute repository root. |
| `stacks` | string[] | The stack ids that were scanned. |
| `stack_source` | string | Where the stacks came from: `audit/stack.json`, `detect_stack.py`, `--stack` or `fallback-all`. |
| `counts` | object | `total`, `http`, `websocket`, `job`, `client-route`, `server-action`, `middleware`. Every key is present, 0 when there are none. |
| `error_shapes.by_file` | {file: string[]} | Error body shapes seen in each file that holds HTTP endpoints. |
| `error_shapes.distinct` | string[] | Union of all shapes. |
| `error_shapes.majority` | string or null | The most common shape. `exception message/stack` is not counted. |
| `sensitive_fields_source` | string | Which list of sensitive names was used: `audit-sensitive-data-catalog (categories: credential, secret)`. |
| `warnings` | string[] | For example, no stack was detected. |
| `endpoints` | record[] | Sorted by kind (http, websocket, server-action, middleware, job, client-route), then path, then method. |

## Record

Enum values are exact strings. The yes/no/unknown facts never use booleans, so a
consumer cannot mistake "not checked" for "no".

### Identity and location

| Key | Values | Meaning |
|---|---|---|
| `id` | `ep-<10 hex>` (`-2`, `-3` suffix on collision) | Stable id, see above. |
| `kind` | `http`, `websocket`, `server-action`, `middleware`, `job`, `client-route` | `server-action`: a Next.js server action, that is a function exported from a `"use server"` module or an inline function containing `"use server"`. It has no URL; the framework calls it by POST to the page that renders it. `middleware`: code that runs before the requests it matches instead of answering one route (Next.js `middleware.ts`, Nuxt `server/middleware`). Both values are additive within 1.0. |
| `stack` | stack id, or `containers` for k8s CronJobs | Next.js and Remix records carry `react` and Nuxt records `vue`, the stacks audit-stack-detection reports for them. |
| `framework` | `aspnet-controller`, `aspnet-minimal-api`, `signalr-hub`, `aspnet-websocket`, `spring-mvc`, `express`, `fastify`, `nestjs`, `nextjs-route`, `nextjs-pages-api`, `nextjs-server-action`, `nextjs-middleware`, `remix-route`, `nuxt-server-route`, `nuxt-server-middleware`, `django-cbv`, `django-fbv`, `django-url`, `drf-apiview`, `drf-api-view`, `drf-viewset`, `drf-viewset-action`, `django-channels`, `flask`, `fastapi`, `angular-router`, `react-router`, `vue-router`, `hangfire`, `hosted-service`, `quartz`, `job-class-by-name`, `spring-scheduled`, `message-listener`, `node-cron`, `cron`, `nestjs-schedule`, `bullmq`, `bull`, `bullmq-nest`, `agenda`, `celery`, `celery-beat`, `apscheduler`, `schedule`, `k8s-cronjob` | The extractor that produced the record. `nextjs-route` comes from the node-express extractor when that stack covers the file, otherwise from the react meta-framework extractor; a handler the first one recorded is not recorded again. |
| `method` | `GET` `POST` `PUT` `PATCH` `DELETE` `HEAD` `OPTIONS` `ANY`, or `WS`, `JOB`, `ROUTE` | `ANY` means the verb is not declared. `server-action` records are `POST` and `middleware` records `ANY`. A Pages Router API route or Remix action that branches on `req.method`/`request.method` gets one record per branch; without branches the API route is `ANY` and the action `POST`. A Remix loader is `GET`; a Nuxt route takes the verb from its `.get`/`.post`/... file suffix, else `ANY`. |
| `path` | string | Normalized full path. Prefixes are joined, `[controller]` and `[action]` are lowercased, constraints are dropped, and `:id`, `<int:pk>` and `[id]` all become `{id}`. For a job it is the job name, else the target, else the trigger. Meta-framework paths come from the file path: `[id]` and `$id` become `{id}`; a catch-all `[...slug]`, `[[...slug]]` or Remix `$` becomes `{slug*}` or `{splat*}`; Next.js `(group)` and `@slot` folders, `index`, Remix `_index`, pathless `_layout` segments and a trailing `_` are dropped. A server action's path is `<file>#<function name>`. A middleware's path is its `config.matcher` entry (one record each), or `*`. |
| `path_raw` | string | Full path as written after prefix joining and token replacement, with constraints kept, for example `/api/v{version:apiVersion}/orders/{id:guid}`. |
| `file`, `line` | string, int | Where the route is declared in the handler's file: the verb attribute, the decorator or the router call. Django and DRF declare routes in urls.py, so there `line` is the handler definition line. |
| `route_location` | {file, line} | Where the route itself is declared. Equal to file/line except for Django urls.py and DRF routers. |
| `handler_line` | int or null | The signature or definition line of the handler. |
| `symbol` | string | `Class.Method`, a function name, `minimal-api`, `inline handler`, or a job target. |
| `class`, `handler` | string or null | The class and the method or function name. |

### auth

| Key | Values | Meaning |
|---|---|---|
| `auth.required` | `yes`, `no`, `unknown` | Whether something in source declares authentication. For jobs and client routes it is always `unknown`. |
| `auth.source` | string | `method attribute`, `class attribute`, `base class attribute (X)`, `global fallback`, `endpoint`, `group ...`, `method annotation`, `class annotation`, `config: <matcher>`, `route middleware`, `router.use (...)`, `mount middleware`, `method guard`, `class guard`, `global APP_GUARD`, `view decorator/mixin/dependency`, `DRF default`, `router dependencies`, `explicit-anonymous`, `none`, `n/a (no HTTP auth)`, `client guard: ...`, `no client guard`, `handler call`, `handler wrapper`, `handler hook`, `next middleware (<file>)`, `server middleware (<file>)`, and a few `... not found` forms. `handler call`: an auth or session call in the handler (getServerSession, auth(), requireUser..., getUserSession, event.context.user and similar). `handler wrapper`: the handler is wrapped in an auth-named function such as `auth(...)` or `withAuth(...)`. `handler hook`: a Nuxt `onRequest` hook with an auth-like name. `next middleware (<file>)` and `server middleware (<file>)`: nothing in the handler, but a middleware in the same project has auth evidence; `required` is then `unknown`, because matchers and path conditions are not evaluated. |
| `auth.anonymous_marker` | string or null | The deliberate anonymous marker that was seen: `[AllowAnonymous]`, `.AllowAnonymous()`, `@PermitAll`, `permitAll()`, `AllowAny`, `@Public()`, `public`. |
| `auth.roles` | string[] | Role names, or role constants such as `CustomRoles.Admin`. |
| `auth.policies` | string[] | Policy, permission, authority or guard names. |
| `auth.evidence` | [{line, text}] | The lines that produced the value. The line is in `file` unless the text starts with another file name. |
| `auth.client_guards` | string[] | Client routes only: `canActivate:authGuard`, `inherited canActivate:authGuard`, `meta.requiresAuth:true`, `element wrapper:RequireAuth`, `global router.beforeEach`. |

### ownership

| Key | Values | Meaning |
|---|---|---|
| `ownership.check` | `yes`, `no`, `unknown`, `n/a` | Only set for HTTP records with an id-like route or query parameter. The version placeholder does not count. `yes`: the handler references the caller's identity (claims, `User.`, `req.user`, principal, tenant context). `unknown`: only owner or tenant key names appear, such as `CompanyId ==`, and their origin is not the caller identity. `no`: neither appears. `n/a`: no id-like selector parameter. For `server-action` records, id-like function arguments and form fields also count as selectors, because the action has no route. |
| `ownership.evidence` | [{line, text}] | The lines that decided `check`. |
| `ownership.identity_refs` | [{line, text}] | Caller-identity references, recorded even when `check` is `n/a`. |
| `ownership.owner_key_refs` | [{line, text}] | Owner or tenant key references. |

### params

`params` is a list of `{name, in, type, id_like, identifier, source_type}`.

- `in` is one of `route`, `query`, `body`, `form` or `header`.
- `identifier` is `tenant` (tenant, company, org, account, branch or workspace ids), `user`
  (user, owner, customer, member, employee, author or created-by ids), `resource` (any
  other id-like name) or null.
- `source_type` names the DTO or serializer when the parameter is a field expanded from a
  request type. It is null for a declared parameter.

`id_params` maps each non-version route placeholder to the key a probe ids file uses.
`{id}` takes the singular of the preceding static segment (`/orders/{id}` becomes
`order`). `{orderId}` becomes `order`, and any placeholder containing `user` becomes `user`.

### request and validation

| Key | Values | Meaning |
|---|---|---|
| `request.types` | string[] | Parameter types defined in the repo. Service types (DbContext, services, loggers) are excluded. |
| `request.has_body` | bool | An explicit body binding, or POST/PUT/PATCH with a request type (typed stacks). On untyped stacks, POST/PUT/PATCH or a read of the request body. Server actions: a declared argument or a body read. |
| `request.body_type` | string or null | The bound body type, for example `CreateOrderDto`, `User`, `string` or `json`. |
| `request.body_type_named_as_dto` | bool or null | True when the body type name ends in Dto/Request/Model/Command/Input/Payload/Form/ViewModel/Query. Null when there is no typed body. |
| `validation.status` | `yes`, `no`, `n/a` | `n/a` when there is no body. `yes` when validation markers appear in the handler or on a request type. |
| `validation.evidence` | string[] | Markers, for example `CreateOrderRequest:[Required`, `@Valid`, `schema:`. |

### response

| Key | Values | Meaning |
|---|---|---|
| `response.type` | string or null | The declared return type, response_model or serializer. |
| `response.returns_collection` | `yes`, `no`, `unknown` | `yes`: a collection type or a materializing call is present. `no`: a declared single type, or single-row fetches only. |
| `response.collection_evidence` | [{line, text}] | |
| `response.pagination.status` | `yes`, `no`, `n/a` | Set for GET/ANY HTTP records that return a collection or whose last segment is not a placeholder. Otherwise `n/a`. |
| `response.pagination.evidence` | string[] | Paging markers, for example `.Skip(`, `PageSize`, `take`, `pagination_class = X`. |
| `response.sensitive_fields` | string[] | `Type.Field` for fields on types named in `response.type` that `audit-sensitive-data-catalog` classifies as credential or secret (`sensitive_fields_source`). Token-issuing endpoints list their token field. |
| `response.returns_entity_like` | bool | Sensitive fields are present, or the handler returns `Ok(_db.X...)` directly. |
| `response.projection` | bool | A select, projection or DTO mapping is visible. |
| `errors.shapes_in_file` | string[] | `{error}`, `{message}`, `{msg}`, `{success:false}`, `ProblemDetails/RFC9457`, `{detail}`, `exception message/stack`. |
| `errors.consistent_with_majority` | `yes`, `no`, `unknown` | Whether the file's shapes equal exactly the repo majority. `unknown` when none are seen. Set for `http` and `server-action` records; the majority comes from files that hold `http` records only. |
| `versioned.status` | `yes`, `no` | `/v<digit>/`, a `{version}` placeholder, `[ApiVersion]` or `@Version`. |
| `versioned.evidence` | string or null | |

### outbound and data_access

| Key | Values | Meaning |
|---|---|---|
| `outbound.calls` | [{file, line, kind, text, awaited, concurrent_group, via}] | HTTP, SMS, mail and queue clients called in the handler or in a one-hop callee. `kind` is `http`, `sms`, `mail` or `queue`. `via` is the callee symbol, for example `OrdersService.create`, or null. `concurrent_group` is true inside Promise.all, Task.WhenAll, asyncio.gather, CompletableFuture.allOf or Mono.zip. |
| `outbound.sequential` | bool | Two or more awaited calls outside a concurrent group, within six lines of each other, where a later call's arguments do not use an earlier call's result variable. |
| `outbound.sequential_evidence` | [{file, line}] | |
| `data_access.db_call_count` | int | Lines with ORM or repository calls. |
| `data_access.materializing_calls` | [{line, text}] | ToList, findMany, findAll, objects.filter and similar. |
| `data_access.paging_seen` | bool | Paging markers appear anywhere in the handler. |
| `data_access.inline_background_work` | bool | Mail, SMS, PDF, Excel or image work appears in the handler. |

### operation, job, notes

| Key | Values | Meaning |
|---|---|---|
| `operation` | `read`, `write`, `list`, `search`, `download`, `export`, `stream`, or null for jobs, client routes and middleware | Fixed rule, applied in order: path contains `download`, then `export`, then a write method, then `search` in the path or a q/term/search query parameter, then collection, then a placeholder or single fetch means `read`, else `list`. Server actions follow the same rule, so they are `write` unless the path contains download or export. |
| `job` | null, or {trigger, name, schedule, target, target_file, target_line, identity_context, evidence} | Jobs only. `identity_context` is `yes` when the target body (or the registration window) references caller identity, owner or tenant keys, the word tenant, or `CustomConnectionString`. Comments are ignored. |
| `notes` | string[] | Neutral extraction notes. |

## endpoints.probe.json

The rows are HTTP records only. Websockets, jobs, client routes and middleware cannot be
probed over plain HTTP, and server actions have no URL (their `path` is
`<file>#<function>`), so all of them are left out.

```json
{"schema_version": "1.0", "base_path": "", "generated_from": "endpoints.json", "note": "...",
 "endpoints": [
  {"id": "ep-3f9c2a1b0d", "method": "GET", "path": "/api/orders/{id}", "route": "/api/orders/{id}",
   "auth_required": true, "auth_source": "class attribute", "roles": ["Admin", "policy:CanRead"],
   "ownership_check": "N", "id_params": {"id": "order"}, "operation": "read",
   "kind": "read", "weight": 1, "tenant_params": ["query:companyId"], "user_params": [],
   "body_fields": ["TenantId", "Total"]}
 ]}
```

| Key | Consumer | Derivation |
|---|---|---|
| `method` | all | The record method. `ANY` becomes `GET` with `"method_assumed": true`. |
| `path` / `route` | authz_probe, tenant_probe / loadtest_plan | `path`, with a `{version}` placeholder replaced by the major version from `[ApiVersion("N...")]`. Without that attribute it stays, and `id_params` gets `version: "version"`. |
| `auth_required` | authz_probe | `yes` gives true, `no` gives false, `unknown` gives null. authz_probe treats null as falsy. |
| `roles` | authz_probe (display) | `auth.roles`, plus `policy:<name>` for each policy. |
| `ownership_check` | authz_probe | `yes` gives `Y`, `no` gives `N`, `n/a` gives `-`, `unknown` gives `?`. |
| `id_params` | authz_probe, tenant_probe | `id_params` from the record. |
| `operation` | tenant_probe | `operation` from the record. |
| `kind` | loadtest_plan | `write` for POST/PUT/PATCH/DELETE, else `read`. |
| `weight` | loadtest_plan | Always 1. |
| `tenant_params`, `user_params`, `body_fields` | informational | The probes ignore these. Use them to add `body`/`query` tamper values by hand. |

The projection never contains `body` or `query`. Tamper payloads are a probe decision,
not an inventory fact.
