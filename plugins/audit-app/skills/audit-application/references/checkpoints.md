# Checkpoint prompts for audit-application

The pauses are user checkpoints: decisions only the application's owner can make. Keep
each prompt to one message, give the options and the default, and record the answer
with `run_state.py`. The mode tells a reader of `audit/run-log.json` who decided:

| Mode | Meaning |
|---|---|
| `interactive` | You asked and the user answered in this conversation. |
| `provided` | The answer came with the invocation (`--profile pre-launch`, `--multi-tenant yes`). |
| `auto-continued` | Nobody could answer (headless `claude -p`, CI, you are a subagent, or `--non-interactive`), so the default below was applied. |

A non-interactive run never skips a checkpoint silently. It applies the default and
records it as `auto-continued`, so the report reader knows which decisions nobody
confirmed. When in doubt whether you can ask, assume you cannot only when there is no
user turn to wait for.

---

## 1. multi-tenant (setup)

**Prompt**

> Before I plan the audit: is this application multi-tenant? That is, does one deployment
> serve several customers or organisations whose data must never mix?
> Hints from the code: {tenancy_signals.tokens, e.g. "CompanyId x5 in OrdersController.cs"}.
> Answer **yes**, **no**, or **not sure** (not sure is treated as yes).

- Source of hints: `python scripts/plan.py <repo> --json` -> `tenancy_signals`.
- **Default (auto-continued):** `yes`. Running the isolation audit on a single-tenant app
  costs one short run that records the tenancy model. Skipping it on a multi-tenant app
  hides the highest-impact class of data leak.
- **Record:** `run_state.py init ... --multi-tenant yes|no` (add `--answers provided` when the
  flag came with the invocation, `--non-interactive` when defaulted).

## 2. prerequisites (setup, confirmation rather than a decision)

**Prompt**

> Detected stack: {backend} + {frontend}. To audit everything the children need:
> {list from references/<stack>.md "Manual trace checklist", e.g. restored packages,
> a buildable project, a read-only DB connection string, a test URL with two user accounts
> and two tenants}. Which of these can you give me? Anything missing is not a blocker:
> the affected checks run without it and the report marks them "limited access".

- **Default (auto-continued):** proceed with what the repo contains; every missing item
  becomes `--limited` on the children that needed it.
- **Record:** no command at this point. Each gap is recorded later on `complete <skill> --limited "<gap>"`.

## 3. scope-profile (setup)

**Prompt**

> Which audit scope?
> 1. **full** - all phases, every audit skill (the long one).
> 2. **security-only** - authz, tenant isolation, injection, secrets, headers, XSS, client auth, dependencies.
> 3. **pre-launch** - authz, tenant isolation, secrets, injection, XSS, business logic, date/time,
>    concurrency, performance, production readiness, dependencies.
> 4. **compliance-only** - privacy data-flow map, GDPR, SOC 2, licensing.
> 5. **custom** - name the skills (for example "authz, secrets, db-schema").
> Every option ends with de-duplication, the OWASP/ASVS mapping and the final report.

- Show `python scripts/plan.py <repo> --profile <choice> --dry-run` if the user wants to see the plan first.
- **Default (auto-continued):** `full`.
- **Record:** `run_state.py init ... --profile <p> [--skills a,b,c]`.

## 4. critical-flows (after discovery)

**Prompt**

> Discovery is done. These look like the business flows where a logic error costs money,
> stock or access (from the code's status enums and domain handlers):
> 1. {flow} - {entry point} ({n} status writes)
> 2. ...
> Which 3-5 should be traced by hand? Reply with numbers, rename them, or add flows I missed
> (webhooks and background jobs count).

- Candidates: `python ../audit-business-logic/scripts/flow_inventory.py <repo> --out audit/evidence/audit-application/flow-candidates.json`.
- **Default (auto-continued):** the top 3-5 candidates. Rank money-moving flows first
  (payments, invoices, refunds, stock), then permissions and approvals, then by number of
  status writes.
- **Record:**
  `run_state.py checkpoint critical-flows --answer "payment; cancellation; stock reservation" --mode interactive --data '{"flows": ["..."], "source": "user"}'`
  -> `run_state.py` writes `audit/evidence/audit-application/checkpoint-critical-flows.json`
  (`{"id", "answer", "mode", "at", "data": {"flows": [...], "source"}}`), passed to
  business-logic, concurrency, datetime and test-coverage.
- Re-asked on resume only if a discovery skill finished after the last answer.

## 5. security-gate (after security)

**Prompt**

> The security phase finished: **{n} Critical** and **{m} High** findings.
> {table from `python scripts/summary.py <repo> --critical-high --phase security`}
> {failed/limited security areas, if any: "Not fully assessed: secrets and config (failed: ...)"}
> Continue with quality, readiness and compliance, or stop now so the team can fix these first?
> If you stop, I will still produce the report for what has run. Re-run with --force after
> fixing, or plain /audit-application to resume the remaining phases.

- **Default (auto-continued):** `continue`. The finished report is more useful than a half
  run, and the findings are already recorded. The answer text records the counts, for
  example `continue (1 Critical, 2 High)`.
- **Record:** `run_state.py checkpoint security-gate --answer "continue" --mode ... --data "$(python scripts/summary.py <repo> --critical-high --json)"`.
- **On stop:** `run_state.py defer --reason "user stopped at security checkpoint to fix findings"`,
  then Phase 6, then `run_state.py finish --outcome "stopped at security gate"`.
- Re-asked on resume when a security skill finished after the last answer. A retried
  security skill can add a Critical, so the user sees the gate again.

---

## Not checkpoints

- `--skill` runs have no checkpoints. The user asked for one child explicitly.
- A child's own clarifying questions (a test URL, the distribution model for licensing, log
  retention) belong to the child. When the orchestrator already holds the answer, pass it in
  the invocation so the user is not asked twice.
