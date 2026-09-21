# Contract checklist: nine properties, evidence, severity

Walk every row of the endpoint table against these nine properties. A
property is *verified* only with a file:line (or config key) as evidence.

## 1. Specification: accurate and not exposed in production

| Check | Evidence that closes it |
|---|---|
| A spec exists and is generated from code (not hand-maintained and stale) | generator package + config (`swashbuckle`, `springdoc`, `swagger-jsdoc`/`@nestjs/swagger`, `drf-spectacular`) |
| Spec matches code: sample 5 endpoints (route, method, request fields, response fields, status codes) | side-by-side notes in evidence |
| Swagger UI / raw spec is not mounted in production, or is behind authentication | environment-gated registration (`if (env.IsDevelopment())`, `springdoc.api-docs.enabled=false` in prod profile, `SPECTACULAR_SETTINGS.SERVE_PERMISSIONS`) |
| Spec does not document internal/admin endpoints publicly | tag/group filtering |

Severity: public spec of a private API = Medium (Low if the API is public by design); stale spec = Low; spec reveals internal admin routes = Medium.

## 2. Versioning strategy

| Check | Evidence |
|---|---|
| A strategy is chosen: path (`/v1/`), header (`Api-Version`), or media type; and documented | routing config, `ApiVersioning` setup, `@RequestMapping("/v1")`, `express.Router()` mounted under `/v1` |
| Every route is versioned (no mix of `/api/orders` and `/api/v2/orders`) | endpoint table column |
| Breaking changes from the spec diff landed in a new version | diff vs version segments |
| Deprecation is signalled (`Deprecation`/`Sunset` headers or spec `deprecated: true`) | header middleware or annotations |

Severity: no versioning with external clients and breaking changes found = Medium; internal-only SPA client = Low/Info.

## 3. Consistent error response shape

One envelope everywhere. Recommended: RFC 9457 problem details
(`application/problem+json`: `type`, `title`, `status`, `detail`, `instance`,
plus `errors` for validation). Acceptable: one custom envelope
(`{ code, message, details[], traceId }`) used by every controller and by the
global exception handler.

| Check | Evidence |
|---|---|
| Global exception handler produces the envelope for unhandled errors | middleware/filter/handler registration |
| Validation errors use the same envelope with per-field detail | `ValidationProblemDetails`, `MethodArgumentNotValidException` handler, zod/joi error mapper, DRF exception handler |
| No controller returns ad-hoc bodies (`new { error }`, `res.json({ msg })`, `Response({"error": ...})`) | grep hits reviewed |
| Stack traces and exception messages are not returned in production | handler strips `detail` outside development |
| Errors never come back as 200 with `success: false` | endpoint table |

Severity: stack traces returned = Medium (CWE-209); two or more shapes = Low (Medium if there are third-party clients).

## 4. Correct HTTP status codes

| Situation | Code | Common mistake |
|---|---|---|
| Created a resource | 201 + `Location` | 200 |
| Deleted / no body | 204 | 200 with empty body |
| Validation failed | 400 (or 422 for semantic) | 500, 200 with error |
| Not authenticated | 401 | 403 |
| Authenticated but not allowed | 403 (or 404 to hide existence) | 401, 200 |
| Missing or other-tenant resource | 404 | 500, 403 leaking existence |
| Duplicate / state conflict / optimistic-lock failure | 409 | 400, 500 |
| Rate limited | 429 + `Retry-After` | 403, 503 |
| Unexpected | 500 with problem body, no trace | 200, 400 |

## 5. Pagination on every list endpoint

| Check | Evidence |
|---|---|
| Every endpoint returning a collection accepts `page`/`pageSize` (or cursor) | handler signature, `Skip/Take`, `Pageable`, `limit/offset`, `PageNumberPagination` |
| `pageSize` has a server-side maximum | clamp code or `max_page_size` |
| Response includes `totalCount` or `nextCursor` and echoes the page | response DTO |
| Sort fields are whitelisted (no arbitrary column names) | switch/whitelist |
| Filters are bounded (date ranges capped) | validation |

Severity: unpaginated list on a table that grows with usage = Medium (High if unauthenticated or returns entities with relations).

## 6. Input validation on every DTO

| Check | Evidence |
|---|---|
| Every bound body/query DTO has required, length, range, format, enum constraints | attributes/annotations/schemas |
| Validation runs automatically (`[ApiController]`, `@Valid`, `ValidationPipe`, serializer `is_valid`) | config |
| Unknown fields rejected or ignored deliberately (`.strict()`, `FAIL_ON_UNKNOWN_PROPERTIES`, `forbidNonWhitelisted`) | config |
| Ids from the route are typed (int/guid), not strings passed to queries | signatures |
| Entities are never bound directly from the request (mass assignment) | separate request DTOs |

Severity: no validation on a write endpoint = Medium (High if it feeds money/state; injection consequences belong to the injection skill).

## 7. Response DTOs do not over-expose entity fields

| Check | Evidence |
|---|---|
| No handler returns an entity/model/ORM object directly | return types, `SELECT *`, `serializer fields = '__all__'` |
| Credential and secret fields never serialise: password/hash/salt/security stamp/API keys/tokens/OTP | `[JsonIgnore]`, `@JsonIgnore`, `exclude`, `write_only=True`, `select: false`, DTO projection |
| Internal fields hidden: soft-delete flags, tenant/company ids of other tenants, audit columns, internal notes, cost price to customers | DTO |
| Navigation/relations not serialised wholesale (cycles, huge payloads) | `ReferenceHandler`, `@JsonManagedReference`, `depth`, explicit DTO |
| Error responses do not include entity dumps | handler |

Severity: credentials/hash/token = High (Critical if unauthenticated); other-tenant identifiers = High in multi-tenant apps; internal flags/cost = Medium; audit columns = Low.

## 8. Consistent naming and date formats

| Check | Evidence |
|---|---|
| JSON property casing consistent (camelCase everywhere) | serializer config, sample responses |
| Paths: plural nouns, kebab-case, no verbs (`/orders/{id}/cancel` is acceptable as an action sub-resource) | endpoint table |
| Ids consistently named (`id`, `orderId`) and typed | DTOs |
| Instants as ISO 8601 with offset (`2024-03-10T09:30:00Z`); dates as `YYYY-MM-DD`; no `dd/MM/yyyy`, no epoch mixes | serializer config, `@JsonFormat`, `DATETIME_FORMAT` (detail owned by the datetime skill) |
| Enums as strings, not ints, unless documented | `JsonStringEnumConverter`, `@Enumerated(STRING)` |
| Booleans not as `"Y"/"N"` or `1/0` strings | DTOs |

Severity: Info/Low; Medium when a client already parses the inconsistent form and a change would break it.

## 9. Breaking-change detection

Breaking: removed path or operation; removed response field; new required request field; type/format change; enum value removed; status code change; auth requirement added; path parameter renamed. Non-breaking: new optional field, new endpoint, new enum value (if clients tolerate), new 4xx code documented.

| Check | Evidence |
|---|---|
| A previous spec exists (git history, release artifact) | path recorded in the report |
| `scripts/spec_diff.py` run and each breaking entry mapped to a version bump or a migration note | `spec-diff.md` |
| CI has a contract-diff step (`oasdiff`, `openapi-diff`, `swagger-diff`) | pipeline file |

Severity: breaking change shipped without a version bump, with external clients = High; internal SPA deployed in lockstep = Low.

## Error-envelope reference (RFC 9457)

```json
{
  "type": "https://api.example.com/problems/validation",
  "title": "One or more validation errors occurred.",
  "status": 400,
  "detail": "quantity must be greater than 0",
  "instance": "/api/v1/orders",
  "traceId": "00-4bf9...-01",
  "errors": { "quantity": ["must be greater than 0"] }
}
```
