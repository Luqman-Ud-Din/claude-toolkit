# Java / Spring reference for audit-frontend-best-practices

This skill audits frontend code. When the repo also contains a Spring Boot
backend, the backend owns only how the SPA's static assets are served. Check
the items below; defer everything else (see the end of this file).

## Stack markers

`pom.xml` / `build.gradle(.kts)` with `spring-boot-starter-web`. Frontend-serving variants:
SPA copied into `src/main/resources/static` (via `frontend-maven-plugin` or Gradle `node` plugin),
Thymeleaf host page, or a separate static host / CDN (then nothing here applies).

## Where the relevant code lives

`application.yml|properties` (`spring.web.resources.*`, `server.compression.*`,
`spring.mvc.static-path-pattern`); a `WebMvcConfigurer` with `addResourceHandlers`;
a forwarding controller for SPA deep links; `pom.xml` `frontend-maven-plugin` `<arguments>`
(which `npm run build` variant); `src/main/resources/static` or `public` contents.

## Dangerous / interesting APIs and patterns (this skill's slice only)

- `server.compression.enabled` absent/false and no compression at the proxy: assets shipped
  uncompressed. Also check `server.compression.mime-types` includes `application/javascript,text/css`.
- `spring.web.resources.cache.cachecontrol.max-age` unset (Spring sends no `Cache-Control`),
  or set globally so `index.html` is cached for a year.
- No `spring.web.resources.chain.strategy.content.enabled=true` and no hashed filenames from
  the frontend build: cache-busting impossible.
- Missing SPA fallback (`@RequestMapping("/{path:[^\\.]*}")` forward to `index.html` or
  `PathResourceResolver` override): deep links 404.
- `*.map` files inside `static/` in the built jar (`jar tf app.jar | grep '\.map$'`).
- `frontend-maven-plugin` executing `npm run build` without the production configuration, or
  `npm start` (dev server) wired into the package phase.
- `spring.web.resources.add-mappings=false` with a hand-rolled handler that lacks cache headers.

## What "good" looks like

```yaml
server:
  compression:
    enabled: true
    mime-types: text/html,text/css,application/javascript,application/json,image/svg+xml
    min-response-size: 1024
spring:
  web:
    resources:
      cache:
        cachecontrol: { max-age: 365d, cache-public: true }
      chain: { strategy: { content: { enabled: true, paths: "/**" } } }
```
```java
@Controller
class SpaForward {
  @RequestMapping(value = "/{path:[^\\.]*}", method = GET)
  public String forward() { return "forward:/index.html"; }
}
@Configuration
class NoCacheIndex implements WebMvcConfigurer {
  public void addResourceHandlers(ResourceHandlerRegistry r) {
    r.addResourceHandler("/index.html").addResourceLocations("classpath:/static/")
     .setCacheControl(CacheControl.noCache());
  }
}
```

## Manual trace checklist

1. Does this backend serve the SPA? Look for `static/index.html` in the build output or a
   forwarding controller. If not, record "backend does not serve frontend" and stop.
2. Compression: Spring property or proxy (`nginx gzip`, ALB)? `curl -I --compressed` closes it.
3. `index.html` cache policy vs hashed chunk policy.
4. Build plugin: production configuration passed; `.map` excluded from `static/`.

## Stack-specific false positives

- Compression left off in Spring but on at the ingress: fine; name the layer.
- `max-age` on hashed assets only: correct.
- Thymeleaf-rendered `index.html` with `no-cache`: correct.

## Tooling

`./mvnw package -DskipTests` then `jar tf target/*.jar | grep -E 'static/.*\.(map|js)$'`;
`curl -I --compressed https://host/assets/main.js`; Spring Boot Actuator `/actuator/configprops`
to read effective `server.compression` values when the app is running.

## Deferred to sibling skills

Security headers / CSP: `audit-security-headers-and-middleware`. API performance and caching:
`audit-performance-and-scalability`. Dependency currency: `audit-dependency-vulnerabilities`.

## References

Spring Boot static content: https://docs.spring.io/spring-boot/reference/web/servlet.html#web.servlet.spring-mvc.static-content;
`server.compression.*` properties reference; CWE-540, ASVS-14.3.2.
