# Area / ID lookup

Same table as SKILL.md, kept here as a standalone reference other skills can
open without loading the full SKILL.md body.

| Area value | ID prefix |
|---|---|
| Prompt Injection | PI |
| Jailbreak Resistance | JB |
| Guardrails | GR |
| Excessive Agency | EA |
| Resource Limits | RL |
| Data Privacy & Isolation | DP |
| Supply Chain | SC |
| Code Execution & Multi-Agent | CE |
| Output Quality | OQ |
| Intent Grounding & Adaptability | IG |
| Prompt & Context Engineering | PE |
| Evals & Red-Teaming | ER |
| Observability & Cost | OC |

## Findings that span two Areas

Example: a finding where a jailbreak succeeds *because* there is no output
guardrail (Jailbreak Resistance + Guardrails). Pick the primary mechanism as
the Area/prefix - here, the missing guardrail is the fixable root cause, so
file it as `LLM-GR-NNN` - and cross-reference the other angle in References
("Related: see also jailbreak reproduction in LLM-JB-004") rather than filing
two findings for one root cause (`audit-finding-writer`'s de-duplication rule
still applies).
