# Java / Spring reference for audit-authz-and-access-control

## Stack markers
`pom.xml`/`build.gradle` with `spring-boot-starter-security` / `spring-boot-starter-web`, `@RestController`, `@SpringBootApplication`. Variants: annotation security (`@PreAuthorize`) vs `SecurityFilterChain` URL rules; MVC vs WebFlux.

## Where the relevant code lives
`*Controller.java` (`@GetMapping` etc.), the `SecurityConfig`/`SecurityFilterChain` bean (URL authorization rules), `*Service.java`/`*Repository.java` (ownership enforcement), request DTOs, `@Scheduled`/listener classes (no HTTP identity).

## Dangerous / interesting APIs and patterns
- Missing auth: a mapping covered by `.permitAll()` / `.anonymous()` in the filter chain, or a controller with no method security when the chain defaults to permit. `@PreAuthorize` absent AND no URL rule = open.
- IDOR: `repository.findById(id)` / `getById(id)` returned without comparing owner/tenant to `SecurityContextHolder.getContext().getAuthentication()` (or an injected `@AuthenticationPrincipal`).
- Mass assignment: binding an `@Entity` directly as `@RequestBody`, or a DTO exposing `role`/`authorities`/`enabled`. Prefer a dedicated request record and `@JsonIgnore`/projection.
- Role enforcement: `@PreAuthorize("hasRole('ADMIN')")`, `.hasRole(...)` / `.hasAuthority(...)` in the chain, method-level `@Secured`. UI-only checks are not enforcement.
- Method security must be enabled (`@EnableMethodSecurity` / `@EnableGlobalMethodSecurity`) or `@PreAuthorize` is silently ignored - verify.

## What "good" looks like
```java
@PreAuthorize("hasRole('CUSTOMER')")
@GetMapping("/orders/{id}")
public OrderDto get(@PathVariable Long id, @AuthenticationPrincipal AppUser me) {
    return orders.findByIdAndCustomerId(id, me.getId())
        .map(OrderDto::from).orElseThrow(NotFound::new);
}
```

## Manual trace checklist
1. Read the `SecurityFilterChain` first - it decides the default. Note every `permitAll`.
2. Confirm `@EnableMethodSecurity` is present if the code relies on `@PreAuthorize`.
3. Trace each `findById` in a controller path to an owner/tenant filter.
4. Check `@Scheduled` tasks and message listeners run with an explicit tenant/user context.

## Stack-specific false positives
`permitAll()` on `/login`, `/actuator/health`, static assets; `findById` inside an admin-scoped method; DTOs with a read-only `role` used only in responses (never bound from a request).

## Tooling
`spotbugs` + `find-sec-bugs`, `mvn dependency-check:check` (OWASP), `spring-boot-actuator` mappings endpoint to list routes. Live probe: `scripts/authz_probe.py`.

## References
CWE-306, CWE-862, CWE-863, CWE-639, CWE-915, CWE-602. ASVS 4.1/4.2, 1.4. OWASP A01:2021.
