# Java / Spring reference for audit-injection-vulnerabilities

## Stack markers
`pom.xml` / `build.gradle(.kts)` containing `spring-boot`. Variants: Spring Data JPA vs JdbcTemplate vs MyBatis/jOOQ; WebMVC vs WebFlux; Kotlin sources (`*.kt`) use the same APIs.

## Where the relevant code lives
`**/repository/**`, `**/dao/**`, `@Repository` classes, `@Query` annotations on repository interfaces, `**/service/**`, `@RestController` methods (sources: `@PathVariable`, `@RequestParam`, `@RequestBody`, `@RequestHeader`, `MultipartFile.getOriginalFilename()`), `resources/**/*.xml` MyBatis mappers (`${}` vs `#{}`), `@Scheduled` and `@KafkaListener`/`@RabbitListener` consumers, `*.ftl`/`*.vm`/`*.html` template loaders.

## Dangerous / interesting APIs and patterns
- SQL: `entityManager.createQuery("... " +`, `createNativeQuery(` with concatenation, `jdbcTemplate.query|update|execute|queryForObject(` with `+` or `String.format`, `Statement.execute|executeQuery|executeUpdate(` (vs `PreparedStatement`), `@Query(value = "..." + )` (rare, but SpEL `?#{...}` and dynamic `ORDER BY` through `Sort` from a raw string), MyBatis `${param}` in mapper XML/annotations, jOOQ `DSL.sql(`/`.plainSQL` with input, `Sort.by(userString)` passed to JPA (JPA validates property names - usually safe, flag as `likely` only when native).
- NoSQL: `BasicQuery(userJson)`, `Query.addCriteria(Criteria.where(field)...)` where `field` is input, `$where`, Elasticsearch `QueryBuilders.wrapperQuery(userJson)`.
- CMD: `Runtime.getRuntime().exec(String)`, `new ProcessBuilder("sh", "-c", ...)`, `ProcessBuilder(cmd + arg)`, Apache Commons `CommandLine.parse(`, Groovy `.execute()` on a string.
- PATH: `new File(base, userName)`, `Paths.get(base, user)` (absolute user value escapes), `Files.readAllBytes|newInputStream|delete|write(`, `FileSystemResource(`, `ResourceLoader.getResource("file:" + `, `MultipartFile.transferTo(new File(... getOriginalFilename()))`, `ClassPathResource(user)`.
- LDAP: `LdapTemplate.search(base, "(uid=" + x + ")"`, `DirContext.search(`, `new LdapQueryBuilder` with `.filter(String)` concatenation (use `.where("uid").is(x)` instead).
- XPATH: `XPath.evaluate("//user[@name='" + x`, `XPathExpression.compile(`, `JXPathContext`; plus `DocumentBuilderFactory` without `disallow-doctype-decl` (XXE, CWE-611).
- TMPL: `new Template(name, new StringReader(userString), cfg)` (FreeMarker), `Velocity.evaluate(ctx, out, tag, userString)`, `SpelExpressionParser().parseExpression(userString)`, Thymeleaf `templateEngine.process(userString, ...)` (inline template), `MessageFormat.format(userString, ...)`, Pebble/Mustache compiling a request string.
- SSRF: `new RestTemplate().getForObject(userUrl`, `WebClient.create().get().uri(userUrl)`, `new URL(userString).openConnection()`, `HttpClient.newHttpClient().send(HttpRequest.newBuilder(URI.create(user)))`, `OkHttpClient` with a request URL from input, `ImageIO.read(new URL(`.
- DESER: `new ObjectInputStream(` on request/queue bytes, `XMLDecoder`, `XStream.fromXML(` without an allow-list, Jackson `enableDefaultTyping()` / `@JsonTypeInfo(use = Id.CLASS)` / `activateDefaultTyping(`, `ObjectMapper.readValue(x, Object.class)`, SnakeYAML `new Yaml().load(` (pre-2.0 or without `SafeConstructor`), Kryo/Hessian on untrusted input, `readObject` in `HttpInvokerServiceExporter`.

## What "good" looks like
```java
// SQL - bind parameters, allow-list sort
List<Sale> rows = em.createQuery("select s from Sale s where s.branchId = :b", Sale.class)
        .setParameter("b", branchId).getResultList();
String sortCol = ALLOWED_SORT.getOrDefault(req.getSort(), "createdOn");
// JdbcTemplate: jdbc.query("select * from sales where branch_id = ?", mapper, branchId);
// MyBatis: #{param} (bound) never ${param} unless allow-listed first.

// PATH
Path root = Paths.get(uploadDir).toAbsolutePath().normalize();
Path target = root.resolve(Paths.get(name).getFileName().toString()).normalize();
if (!target.startsWith(root)) throw new AccessDeniedException(name);

// CMD
new ProcessBuilder("convert", target.toString(), out.toString()).start();   // no shell, list form

// SSRF
URI u = URI.create(input); if (!"https".equals(u.getScheme()) || !ALLOWED_HOSTS.contains(u.getHost())) throw ...;

// DESER - Jackson default typing off; ObjectInputFilter (JEP 290) allow-list if Java serialization is unavoidable.
```

## Manual trace checklist
1. Every `@RequestParam String sort`/`order`/`filter` that reaches a native query, Criteria API string, or MyBatis `${}`.
2. Search endpoints using `Specification`/`Criteria` built from arbitrary field names (`root.get(userField)`) - usually safe (property must exist) but flag native SQL fallbacks.
3. File upload/download controllers and static-resource handlers using `getOriginalFilename()`.
4. Any bean that calls `RestTemplate`/`WebClient` with a URL from a DTO, a database row edited by users, or a webhook registration.
5. Message consumers deserializing `byte[]` payloads; `spring-boot-starter-activemq`/`rabbit` with `SimpleMessageConverter` (Java serialization).
6. Spring Expression usage in `@PreAuthorize`/`@Value`/`@Query` that concatenates user text.

## Stack-specific false positives
- `@Query("... where s.id = :id")` and `?1` positional params are bound.
- `Runtime.exec(new String[]{...})` with array form and constant program.
- `new File(base, "report.pdf")` with constant name.
- `RestTemplate` with a URL from `application.yml` plus a numeric id.
- `Yaml(new SafeConstructor(...))`, SnakeYAML >= 2.0 defaults, Jackson without default typing.

## Tooling
- `mvn com.github.spotbugs:spotbugs-maven-plugin:check` with `findsecbugs` plugin (SQL_INJECTION_*, COMMAND_INJECTION, PATH_TRAVERSAL_IN, OBJECT_DESERIALIZATION, URLCONNECTION_SSRF_FD).
- `semgrep --config p/java --config p/spring`.
- `mvn org.owasp:dependency-check-maven:check` for known deserialization gadget chains (report those under audit-dependency-vulnerabilities).

## References
OWASP Java Injection Prevention and Deserialization cheat sheets; Spring Data JPA "Query Methods"; MyBatis `#{}` vs `${}` docs; JEP 290 serialization filtering. CWE-89, 78, 22, 90, 643, 918, 502, 1336, 917 (EL injection); ASVS 5.3.x, 5.5.x, 12.3.x, 12.6.1; OWASP A03/A08/A10:2021.
