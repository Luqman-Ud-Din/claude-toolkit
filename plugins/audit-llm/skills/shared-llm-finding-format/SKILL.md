---
name: shared-llm-finding-format
description: The single definition of the LLM audit finding template, its Area values, and its ID scheme (LLM-<AREA>-<NNN>) - an extension of the existing audit-finding-writer format, not a replacement for it. Defines which of the 13 Area values (Prompt Injection, Jailbreak Resistance, Guardrails, Excessive Agency, Resource Limits, Data Privacy & Isolation, Supply Chain, Code Execution & Multi-Agent, Output Quality, Intent Grounding & Adaptability, Prompt & Context Engineering, Evals & Red-Teaming, Observability & Cost) each audit-llm-* skill uses. This is a shared building block, not run standalone - every audit-llm-* skill writes findings this way, and propose-llm-* skills read them. Use it whenever a skill needs to know which Area value, ID prefix, or References format to use for an LLM-specific finding.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-llm:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Shared: LLM finding format

Design principle 5: reuse the existing library. Findings are still written
through `audit-finding-writer`, de-duplicated with `audit-findings-rollup`, and
published with `audit-report-generator` - exactly the machinery every other
`audit-*` skill uses. This skill supplies only the three things that are
specific to LLM findings: the **Area** value, the **ID prefix**, and how the
**References** field cites LLM/agentic standards. Everything else (severity
scale, field order, tone, de-duplication, the `findings.json` shape) is
`audit-finding-writer`'s contract, unchanged - read that skill, not this one,
for those.

## Area values and ID prefixes

| Area value | ID prefix | OWASP anchor | Written by |
|---|---|---|---|
| Prompt Injection | PI | LLM01, ASI01 | audit-llm-prompt-injection |
| Jailbreak Resistance | JB | LLM01, LLM07 | audit-llm-jailbreak-resistance |
| Guardrails | GR | LLM05 | audit-llm-guardrails |
| Excessive Agency | EA | LLM06, ASI02, ASI03 | audit-llm-excessive-agency |
| Resource Limits | RL | LLM10, ASI08 | audit-llm-resource-limits |
| Data Privacy & Isolation | DP | LLM02, LLM08, ASI06 | audit-llm-data-privacy-and-isolation |
| Supply Chain | SC | LLM03, LLM04, ASI04 | audit-llm-supply-chain |
| Code Execution & Multi-Agent | CE | ASI05, ASI07 | audit-llm-code-execution-and-multi-agent |
| Output Quality | OQ | LLM09, ASI09 | audit-llm-output-quality |
| Intent Grounding & Adaptability | IG | ASI01, ASI10 (partial) | audit-llm-intent-grounding-and-adaptability |
| Prompt & Context Engineering | PE | (no direct OWASP id - best practice) | audit-llm-prompt-and-context-engineering |
| Evals & Red-Teaming | ER | (no direct OWASP id - best practice) | audit-llm-evals-and-red-teaming |
| Observability & Cost | OC | LLM10 | audit-llm-observability-and-cost |

`NNN` is a per-skill, per-run sequence starting at 001, the same way other
`audit-*` skills number their prefix - `LLM-PI-001`, `LLM-PI-002`, etc. Never
reuse a number across skills; `LLM-PI-001` and `LLM-EA-001` are unrelated
findings and can coexist.

## The finding block

Identical to `audit-finding-writer`'s block (Location, Confidence, Evidence,
Impact, Remediation, References - see `$AUDIT_CORE_ROOT/skills/audit-finding-writer/SKILL.md`),
with two differences:

1. **Title line** carries the LLM ID instead of a generic prefix:
   `### [Severity] LLM-PI-001 - Title in one clause`
2. **References** always includes the OWASP LLM/Agentic anchor from the table
   above, and should add the MITRE ATLAS technique or NIST AI RMF control when
   one applies - use `shared-llm-owasp-mapping` to fill this in rather than
   guessing an id.

```markdown
### [High] LLM-EA-003 - refund_order tool has no approval gate before an irreversible action
- **Location:** `src/agent/tools/refund_order.py:1` (refund_order)
- **Confidence:** confirmed
- **Evidence:**

```python
tools = [refund_order]  # agent calls this directly, no confirmation step
```

- **Impact:** A successful prompt injection or a model reasoning error can trigger a real refund with no human check, at any amount the model is convinced to pass.
- **Remediation:** Split into propose_refund (returns a pending id) and confirm_refund (requires a signed operator token); the agent can only call propose_refund.
- **References:** OWASP LLM06:2025 / ASI02:2026 (Excessive Agency); MITRE ATLAS AML.T0053 (LLM Plugin Compromise); Related: LLM-PI-001
```

## Severity

Use `audit-finding-writer`'s rubric unchanged (`$AUDIT_CORE_ROOT/skills/audit-finding-writer/references/severity-rubric.md`).
One LLM-specific calibration note: rate an *exploitable* prompt injection or
jailbreak that only produces off-brand text (no data access, no tool call, no
policy-relevant disclosure) as Medium at most - severity tracks real-world
impact, not "the model said something it shouldn't", per the same rubric's
exploitability × impact reasoning.

## Emitting a finding

Call `audit-finding-writer` exactly as any other audit skill does, passing
the Area value and `LLM-<PREFIX>-NNN` id instead of that skill's default
prefix scheme; write to `audit/findings/audit-llm-<skill-suffix>.json` per
`shared-llm-handoff-contract`.

## Bundled files

- `references/area-id-map.md` - this skill's table as a standalone lookup, plus guidance for a finding that spans two Areas (pick the primary mechanism, cross-reference the other in References).
