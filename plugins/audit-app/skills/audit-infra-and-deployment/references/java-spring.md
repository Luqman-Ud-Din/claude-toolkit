# Java / Spring Boot reference for audit-infra-and-deployment

## Stack markers
- `pom.xml` / `build.gradle(.kts)` with `spring-boot-starter-*`; `mvnw`, `gradlew`.
- Image build styles, most common first:
  1. Hand-written `Dockerfile` (fat jar or layered jar).
  2. Cloud Native Buildpacks: `./mvnw spring-boot:build-image` / `./gradlew bootBuildImage` (Paketo). Runs as the non-root `cnb` user; no Dockerfile.
  3. Jib: `jib-maven-plugin` / `com.google.cloud.tools.jib`. Distroless base by default; user set with `jib.container.user`.
- Deployment: Kubernetes/Helm, `manifest.yml` (Cloud Foundry), `app.yaml` (App Engine), `Procfile`, `appspec.yml` (CodeDeploy).

## Where the relevant code lives
- `Dockerfile`, and `pom.xml` `<plugin>` blocks for buildpacks/Jib (`<image><name>`, `<from><image>`, `<container><user>`).
- `src/main/resources/application.yml` / `application-{profile}.yml`: actuator, graceful shutdown, forwarded headers, profiles (environment parity).
- `db/migration` (Flyway `V1__*.sql`, `U1__*.sql` undo) or `db/changelog` (Liquibase): migration and rollback strategy.

## Dangerous / interesting APIs and patterns
Images:
- Final stage `FROM maven:*`, `gradle:*`, `eclipse-temurin:*-jdk*` or `openjdk:*` (a deprecated image) ships a JDK and build tools. The runtime should be `eclipse-temurin:21-jre-alpine` / `-jre-jammy`, `gcr.io/distroless/java21-debian12:nonroot`, or `bellsoft/liberica-runtime-container:jre-21-slim-musl`.
- A fat jar copied as one layer means every code change re-pushes all dependencies. Use layered jars:
  - Boot 3.3+: `java -Djarmode=tools -jar app.jar extract --layers --launcher --destination extracted`
  - Boot 2.3-3.2: `java -Djarmode=layertools -jar app.jar extract`
  - Copy `dependencies/`, `spring-boot-loader/`, `snapshot-dependencies/` and `application/` in that order. The entrypoint is `org.springframework.boot.loader.launch.JarLauncher` (3.2+) or `org.springframework.boot.loader.JarLauncher` (older).
- No `USER`: temurin images run as root. Add `RUN addgroup --system spring && adduser --system --ingroup spring spring` (Debian) or `addgroup -S spring && adduser -S spring -G spring` (Alpine), then `USER spring:spring`.

JVM and memory:
- A hard-coded `-Xmx2g` in `ENTRYPOINT` or `JAVA_TOOL_OPTIONS` that exceeds the pod memory limit gets the pod OOMKilled. Prefer `-XX:MaxRAMPercentage=75.0` (JDK 10+ is container-aware).
- `-agentlib:jdwp=transport=dt_socket,server=y,address=*:5005` leaves a remote debugger open in production.

Health, shutdown, proxy:
- `management.endpoint.health.probes.enabled=true` (auto-enabled on Kubernetes) exposes `/actuator/health/liveness` and `/actuator/health/readiness`. Probes that point at `/actuator/health` make liveness depend on the database.
- `management.endpoints.web.exposure.include=*` makes heapdump, env and threaddump reachable. Put actuator on a `management.server.port` that the Service/Ingress does not expose.
- Set `server.shutdown=graceful` and `spring.lifecycle.timeout-per-shutdown-phase=20s`, below `terminationGracePeriodSeconds`.
- TLS terminated upstream needs `server.forward-headers-strategy=framework` (or `native`); otherwise redirects and `request.isSecure()` are wrong.

Secrets:
- A literal `SPRING_DATASOURCE_PASSWORD` in a manifest or `ENV`, or an `application-prod.yml` with credentials copied into the image.
- Good: Spring Cloud Vault (`spring.cloud.vault.*`), `spring.config.import=optional:configtree:/run/secrets/`, AWS/Azure/GCP secret-manager starters, `secretKeyRef`.

Migrations and rollback:
- `spring.flyway.enabled=true` on every replica start is usually fine because Flyway takes a lock. But rolling back to the previous jar fails validation if a newer migration exists (`spring.flyway.validate-on-migrate`), so plan expand/contract migrations. Flyway undo migrations are a paid (Teams/Enterprise) feature; Liquibase has `rollback` tags.

## What "good" looks like
```dockerfile
FROM eclipse-temurin:21-jdk-jammy@sha256:<digest> AS build
WORKDIR /workspace
COPY mvnw pom.xml ./
COPY .mvn .mvn
RUN ./mvnw -B dependency:go-offline
COPY src src
RUN ./mvnw -B package -DskipTests && java -Djarmode=tools -jar target/*.jar extract --layers --launcher --destination extracted

FROM eclipse-temurin:21-jre-alpine@sha256:<digest>
RUN addgroup -S spring && adduser -S spring -G spring
USER spring:spring
WORKDIR /app
COPY --from=build /workspace/extracted/dependencies/ ./
COPY --from=build /workspace/extracted/spring-boot-loader/ ./
COPY --from=build /workspace/extracted/snapshot-dependencies/ ./
COPY --from=build /workspace/extracted/application/ ./
ENV JAVA_TOOL_OPTIONS="-XX:MaxRAMPercentage=75.0"
ENTRYPOINT ["java", "org.springframework.boot.loader.launch.JarLauncher"]
```

## Manual trace checklist
1. Which build style produces the image (Dockerfile, buildpacks, Jib), and which user and base it ends up with (`docker inspect`).
2. Probes use the liveness/readiness groups, and actuator is not exposed publicly.
3. JVM heap against the container memory limit; graceful shutdown against the termination grace period.
4. For every datasource and credential property, its source in the running environment.
5. The migration tool, and whether the previous release still starts against the migrated schema (rollback compatibility).
6. Profiles per environment (`application-staging.yml` vs `application-prod.yml`) should have the same keys with only the values differing.

## Stack-specific false positives
- `maven`/`*-jdk` images in a non-final stage.
- No Dockerfile, but `spring-boot:build-image` or Jib is configured. The image is still built, and is non-root by default.
- `-Xmx` set together with a larger memory limit that leaves headroom.
- `management.endpoints.web.exposure.include=health,info,prometheus` is scoped and fine.

## Tooling
- `./mvnw spring-boot:build-image -Dspring-boot.build-image.imageName=app:1.2.3`; `pack inspect app:1.2.3`.
- `hadolint Dockerfile`, `trivy config .`, `checkov -d .`, `kube-score score k8s/*.yaml`.
- `java -Djarmode=tools -jar app.jar list-layers` to confirm the jar is layered.

## References
- Spring Boot docs: "Efficient Container Images", "Kubernetes probes", "Graceful shutdown", "Running behind a front-end proxy server".
- Eclipse Temurin and distroless Java image docs; Jib FAQ (user, base image).
- CIS Docker Benchmark 4.1/4.3; CWE-250, CWE-489 (debug port), CWE-798.
