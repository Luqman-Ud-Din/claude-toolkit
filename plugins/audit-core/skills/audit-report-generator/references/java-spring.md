# Java / Spring reference for audit-report-generator

What the report should enumerate and how to phrase findings when the backend is Spring
Boot. The generator is stack-agnostic; this file guides the reviewer's scope table,
executive wording and remediation grouping.

## Stack markers
`pom.xml` / `build.gradle(.kts)` with `spring-boot-starter-*`, `@SpringBootApplication`,
`application*.yml|properties`, `src/main/resources/db/migration` (Flyway/Liquibase).
Multi-module builds: one scope row per deployable module.

## Where the relevant code lives (what "Scope" must enumerate)
- Deployable modules (each `spring-boot-maven-plugin` / `bootJar` module).
- Entry points: `@RestController` / `@Controller` classes, `@Scheduled` jobs, `@KafkaListener` / `@RabbitListener` consumers, actuator endpoints.
- Security config: every `SecurityFilterChain` bean (there may be several, ordered).
- Config surfaces: `application-{profile}.yml`, Spring Cloud Config, Vault; say which profile was reviewed as "production".
- Out-of-repo pieces for "Not checked": Kubernetes ingress / API gateway config, Keycloak realm settings, JVM flags.

## Findings that are typical launch blockers (and how to phrase them)
| Engineering finding | Executive wording |
|---|---|
| `permitAll()` on `/api/admin/**` or a chain without `.anyRequest().authenticated()` | "Administrative functions are reachable without logging in." |
| Repository query without owner/tenant predicate (`findById` from a path variable) | "One customer can read or change another customer's records." |
| `nativeQuery = true` with string concatenation, `JdbcTemplate` with `+` | "A crafted input can read or delete the whole database." |
| Password or API key literal in `application.yml` committed | "Anyone with repository access can connect to production systems." |
| Actuator `env`/`heapdump` exposed without auth | "Visitors can download server memory and configuration, including secrets." |
| `enableDefaultTyping()` / `ObjectInputStream` on request bodies | "A crafted request can run arbitrary code on the server." |

## What "good" looks like (remediation plan wording)
- "Add `.anyRequest().authenticated()` at the end of the API chain; add a MockMvc test expecting 401."
- "Replace `findById(id)` with `findByIdAndOwnerId(id, principal.id)` in `OrderRepository`."
- "Bind parameters with `:name` in the `@Query`; delete the string concatenation."
- "Move secrets to Vault (`spring.cloud.vault`) or env placeholders `${DB_PASSWORD}`; rotate."
- "Set `management.endpoints.web.exposure.include=health,info`."
Group tickets by `SecurityConfig` (all chain items), by repository (all ownership items), by profile file (all secrets items).

## Report review checklist (manual trace)
1. Scope table lists every `SecurityFilterChain` bean reviewed and the profile treated as production.
2. Actuator exposure appears as checked or not checked.
3. Message consumers and scheduled jobs are in scope (they bypass HTTP security).
4. Dependency findings cite `dependency-check` or `mvn versions:display-dependency-updates` output in the evidence appendix.
5. Every Critical/High cites a class in `src/main`, not `src/test`.

## Stack-specific false positives
- `csrf().disable()` on a stateless bearer-token API (document as N/A, not a finding).
- `permitAll()` on `/actuator/health`, `/login`, `/swagger-ui/**` in non-prod profiles.
- `@Query(nativeQuery = true)` using `:param` binding.
- `NoOpPasswordEncoder` in a test profile only.

## Tooling (evidence to expect in Appendix B)
`mvn org.owasp:dependency-check-maven:check` HTML/JSON report, SpotBugs + find-sec-bugs
output, `curl -sI` header dumps, `jcmd`/`jmap` summaries for leak findings.
Export: `pandoc audit/audit-report.md -o audit/audit-report.pdf --toc --from gfm --pdf-engine=xelatex`.

## Executive glossary (translate before the summary goes out)
- "SecurityFilterChain" -> "the rules that decide who may call which URL".
- "actuator" -> "the built-in diagnostics pages".
- "profile" -> "the configuration set used in production".
- "native query" -> "hand-written database query".

## References
Spring Security reference (Authorize HttpServletRequests, CSRF, Headers); Spring Boot Actuator security;
OWASP ASVS 4.0.3 V4, V5.3, V14.3; CWE-306, CWE-639, CWE-89, CWE-502, CWE-798.
