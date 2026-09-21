# OWASP LLM / Agentic mapping table

OWASP Top 10 for LLM Applications (2025) ids are well-established. OWASP Top
10 for Agentic Applications (2026) ids below are best-effort as of this
writing (2026-09) - verify against the current published revision before
citing an ASI id in a compliance-facing document (see the caveat in SKILL.md).

| Area | OWASP LLM (2025) | OWASP Agentic (2026, best-effort) | Representative MITRE ATLAS technique | NIST AI RMF function |
|---|---|---|---|---|
| Prompt Injection | LLM01: Prompt Injection | ASI01: Agent Authorization & Control Hijacking | AML.T0051 (LLM Prompt Injection) | Manage |
| Jailbreak Resistance | LLM01: Prompt Injection; LLM07: System Prompt Leakage | ASI01 (related) | AML.T0054 (LLM Jailbreak) | Manage |
| Guardrails | LLM05: Improper Output Handling | ASI01 (related, enforcement gap) | AML.T0050 (Command and Scripting Interpreter via LLM output) | Manage |
| Excessive Agency | LLM06: Excessive Agency | ASI02: Agent Critical Systems Interaction; ASI03: Agent Untraceability | AML.T0053 (LLM Plugin Compromise) | Govern, Manage |
| Resource Limits | LLM10: Unbounded Consumption | ASI08: Agent Resource & Cost Exhaustion | AML.T0034 (Cost Harvesting) | Manage |
| Data Privacy & Isolation | LLM02: Sensitive Information Disclosure; LLM08: Vector and Embedding Weaknesses | ASI06: Agent Memory & Context Poisoning / Privacy | AML.T0057 (LLM Data Leakage) | Map, Manage |
| Supply Chain | LLM03: Supply Chain; LLM04: Data and Model Poisoning | ASI04: Agent Supply Chain & Dependency Attacks | AML.T0010 (ML Supply Chain Compromise) | Govern |
| Code Execution & Multi-Agent | (no single direct LLM anchor - overlaps LLM05) | ASI05: Agent Unexpected Code Execution; ASI07: Agent-to-Agent / Communication Poisoning | AML.T0011 (User Execution) | Manage |
| Output Quality | LLM09: Misinformation | ASI09: Agent Hallucination & Goal Misalignment | AML.T0048 (LLM Hallucination-driven output) | Measure |
| Intent Grounding & Adaptability | (best practice - no direct LLM anchor) | ASI01 (partial); ASI10: Intent Breaking & Goal Manipulation | AML.T0054 (related) | Map |
| Prompt & Context Engineering | (best practice - no direct LLM anchor) | (no direct anchor - design quality) | - | Map |
| Evals & Red-Teaming | (best practice - no direct LLM anchor) | (no direct anchor - process control) | - | Measure |
| Observability & Cost | LLM10: Unbounded Consumption | (overlaps ASI08) | AML.T0034 (Cost Harvesting) | Measure, Manage |

## Notes

- Several Areas ("Prompt & Context Engineering", "Evals & Red-Teaming") are
  best-practice categories with no dedicated OWASP LLM/Agentic id - that's
  expected; cite the closest NIST AI RMF function and say plainly in the
  finding that there is no direct OWASP anchor, rather than forcing a mapping.
- When both an LLM and an Agentic id apply, cite both:
  `OWASP LLM06:2025 / ASI02:2026`.
- ATLAS technique ids are representative, not exhaustive - a finding can cite
  a more specific technique than the table's default if the audit skill
  traced the mechanism precisely enough to justify it.
