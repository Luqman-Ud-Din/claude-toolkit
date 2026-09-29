# Changelog

## 0.1.1 - 2026-09-29

- Pin audit-production-readiness-checklist's expected-skill roster to audit-application's profiles.json so a new audit cannot silently drop a go/no-go caveat.
- Compile audit-test-coverage-and-ci's gate patterns once at module level; scan output is unchanged.
- Remove unreachable helpers and unused imports across audit-frontend-best-practices, audit-technical-debt, audit-dependency-vulnerabilities and audit-infra-and-deployment.

## 0.1.0 - 2026-09-21

- Initial marketplace packaging of existing skills, including supporting files and eval fixtures.
- Preserve skill IDs and audit output paths; use plugin namespaces for invocation.
- Resolve shared scripts through the audit-core plugin.
