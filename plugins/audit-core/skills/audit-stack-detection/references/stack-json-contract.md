# audit/stack.json contract

Owned by `audit-stack-detection`. Written once per audit; read by every audit skill.

## Schema

| Field | Type | Meaning |
|---|---|---|
| `detected_at` | ISO-8601 string | When detection ran. |
| `root` | string | Absolute path of the audited repository. |
| `stacks` | array | One entry per detected stack id, sorted by id. |
| `stacks[].id` | string | One of the supported ids below. |
| `stacks[].reference` | string or null | File name consumers open under their own `references/`. `null` for `containers`. |
| `stacks[].evidence` | array of strings | Repo-relative marker files that triggered detection. A note in parentheses marks a weak match. |
| `stacks[].roots` | array of strings | Repo-relative folders holding each marker; one per sub-project. |
| `primary_backend` | string or null | First backend id found. |
| `primary_frontend` | string or null | First frontend id found. |
| `multi_tenant` | true, false or null | Set only by `audit-application` after asking the user. |

## Supported ids and markers

| Id | Markers | Kind |
|---|---|---|
| `dotnet` | `*.csproj`, `*.sln`, `*.fsproj` | backend |
| `java-spring` | `pom.xml`, `build.gradle`, `build.gradle.kts` (Spring marker checked; plain Java noted) | backend |
| `node-express` | `package.json` depending on express, fastify, koa, @nestjs/core, hapi | backend |
| `python-django` | `manage.py`, or `requirements.txt` / `pyproject.toml` / `Pipfile` / `setup.py` naming django; Flask and FastAPI noted | backend |
| `angular` | `package.json` depending on @angular/core | frontend |
| `react` | `package.json` depending on react or next | frontend |
| `vue` | `package.json` depending on vue or nuxt | frontend |
| `containers` | `Dockerfile`, `*.dockerfile`, `docker-compose.yml|yaml` | infra |

Folders skipped during detection: `.git`, `node_modules`, `bin`, `obj`, `dist`,
`build`, `target`, `.venv`, `venv`, `__pycache__`, `.idea`, `.vs`, `packages`,
`coverage`, `.angular`, `.next`, `audit`. Depth is limited to four levels below the root.

## Rules for consumer skills

1. Read `audit/stack.json` if it exists. Otherwise run
   `../audit-stack-detection/scripts/detect_stack.py <repo>` without `--write`, so a
   standalone run does not create state the orchestrator would later trust.
2. Open only `references/<id>.md` for the ids present. When several stacks are
   present, open one file per stack and keep their findings separate by root.
3. If an id has no reference file in the consumer, fall back to the stack reference
   template and list the stack under "Not checked" with the reason.
4. Never edit `audit/stack.json` from a consumer skill.

## Known limits

- Next.js and Nuxt server routes are reported as frontend only.
- Gradle Kotlin DSL projects without a Spring plugin are reported as Java with a note.
- Go, Ruby, PHP, Rust and Elixir are not detected. Add them through the template.
