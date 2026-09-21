# Java / Spring reference for audit-api-contract

## Stack markers
`pom.xml` / `build.gradle` with `spring-boot-starter-web` (or `webflux`). Variants: springdoc-openapi vs springfox; Spring HATEOAS; Spring Data REST (auto-exposes repositories: audit `@RepositoryRestResource`); API versioning via path, `@RequestMapping(headers=...)`, or `produces=` media type.

## Where the relevant code lives
- Spec: `application*.yml` (`springdoc.api-docs.enabled`, `springdoc.swagger-ui.enabled`, `springdoc.api-docs.path`), `OpenAPI` bean config, security config (`permitAll()` on `/v3/api-docs/**`, `/swagger-ui/**`).
- Routes: `@RestController`, `@RequestMapping("/api/v1/...")`, `@GetMapping`/`@PostMapping`; Spring Data REST base path.
- DTOs: `dto/`, `request/`, `response/`; validation via Bean Validation (`@NotNull`, `@Size`, `@Min`, `@Email`, `@Pattern`, `@Valid` on nested), `@Validated`.
- Errors: `@ControllerAdvice` + `@ExceptionHandler`, `ProblemDetail` (Spring 6), `spring.mvc.problemdetails.enabled=true`, `ResponseStatusException`, `server.error.include-stacktrace`.
- Pagination: `Pageable`, `Page<T>`, `Slice<T>`, `spring.data.web.pageable.max-page-size`.
- Serialisation: Jackson `spring.jackson.property-naming-strategy`, `@JsonIgnore`, `@JsonProperty(access = WRITE_ONLY)`, `@JsonFormat`, `WRITE_DATES_AS_TIMESTAMPS`.

## Dangerous / interesting APIs and patterns
- Spec exposure: `springdoc.api-docs.enabled` not `false` in the prod profile; security config `permitAll()` for `/v3/api-docs/**` and `/swagger-ui/**`; springfox `/v2/api-docs` left on.
- Entity returned: `ResponseEntity<User>`, `List<Order>` from `repository.findAll()`, `@RepositoryRestResource` exposing entities with `password`, `passwordHash`, `salt`, `apiKey`, `token`, `tenantId`; missing `@JsonIgnore`/`WRITE_ONLY`; lazy relations serialised (`LazyInitializationException` or huge payloads).
- Unpaginated: `findAll()` returning `List`, `@GetMapping` without `Pageable`; `max-page-size` default (2000).
- Validation: `@RequestBody` without `@Valid`; DTO fields without constraints; `@Valid` missing on nested lists (`List<@Valid LineDto>`); entity bound as `@RequestBody`.
- Error shape: `return ResponseEntity.badRequest().body(Map.of("error", ...))`, `new ErrorResponse(...)` in one controller and `ProblemDetail` in another; no `@ControllerAdvice`; `server.error.include-message=always`/`include-stacktrace=always` in prod; Spring's default whitelabel JSON (`timestamp,status,error,path`) mixed with custom shapes.
- Status codes: `@PostMapping` returning 200 (no `@ResponseStatus(CREATED)`); `ResponseStatusException(HttpStatus.UNAUTHORIZED)` for forbidden; `Optional.orElseThrow()` -> 500 instead of 404.
- Naming/dates: `PropertyNamingStrategies.SNAKE_CASE` in one module only; `WRITE_DATES_AS_TIMESTAMPS=true` (epoch millis) vs ISO elsewhere; `LocalDateTime` fields (no offset); enums by ordinal.
- Versioning: no version segment; `@RequestMapping(value="/orders", version=...)` absent; `@Deprecated` without `Deprecation` header.

## What "good" looks like
```yaml
# application-prod.yml
springdoc: { api-docs: { enabled: false }, swagger-ui: { enabled: false } }
spring: { mvc: { problemdetails: { enabled: true } }, jackson: { serialization: { write-dates-as-timestamps: false } }, data: { web: { pageable: { max-page-size: 100 } } } }
server: { error: { include-stacktrace: never, include-message: never } }
```
```java
@RestController @RequestMapping("/api/v1/orders")
class OrdersController {
    @GetMapping Page<OrderDto> list(@PageableDefault(size = 20) Pageable pageable) { return service.list(pageable).map(OrderDto::from); }
    @PostMapping @ResponseStatus(HttpStatus.CREATED) OrderDto create(@Valid @RequestBody CreateOrderRequest req) { ... }
}
record CreateOrderRequest(@NotEmpty List<@Valid LineRequest> lines, @Size(max = 32) String couponCode) {}
@RestControllerAdvice class ApiErrors extends ResponseEntityExceptionHandler { @ExceptionHandler(NotFoundException.class) ProblemDetail notFound(NotFoundException e) { return ProblemDetail.forStatusAndDetail(HttpStatus.NOT_FOUND, e.getMessage()); } }
class User { @JsonIgnore String passwordHash; }
```

## Manual trace checklist
1. Prod profile: springdoc flags; security `permitAll` list; `server.error.*`.
2. Endpoint table: `@GetMapping` returning `List`/`Iterable` without `Pageable`; return types that are `@Entity` classes.
3. `@RequestBody` parameters: `@Valid` present; DTO constraints; nested `@Valid`.
4. `@ControllerAdvice` coverage; any `Map.of("error"`/custom error classes per controller.
5. Spring Data REST: any `@RepositoryRestResource` (exposes everything unless `exported = false`).
6. Spec diff: previous `/v3/api-docs` snapshot from git or CI artifact vs current (`curl localhost:8080/v3/api-docs` on a dev run) via `scripts/spec_diff.py`.

## Stack-specific false positives
- `ResponseEntity<Entity>` for entities with no sensitive fields and `@JsonIgnore` on relations (recommend DTO, Info).
- `Page<T>` with default `max-page-size` overridden globally.
- springdoc enabled in prod behind an authenticated gateway (confirm and record).
- Spring's default error JSON if it is the *only* shape and `include-stacktrace=never`.

## Tooling
`grep -rn "springdoc\|springfox" src/main/resources pom.xml build.gradle`; `grep -rn "ResponseEntity<\(User\|Order\|Product\)\b\|List<\(User\|Order\)>" --include=*.java`; `grep -rn "@RequestBody" --include=*.java | grep -v "@Valid"`; `$AUDIT_CORE_ROOT/skills/audit-endpoint-inventory/scripts/inventory_endpoints.py`; `oasdiff` or `scripts/spec_diff.py`.

## References
ASVS 13.1/13.2, OWASP API Security Top 10 2023, RFC 9457, Spring `ProblemDetail` docs, springdoc configuration properties, Spring Data REST security notes.
