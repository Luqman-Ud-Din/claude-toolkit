# Child skill selection rules

| Skill | Runs when |
|---|---|
| audit-llm-prompt-injection | Always (any detected LLM feature) |
| audit-llm-jailbreak-resistance | Always |
| audit-llm-guardrails | Always |
| audit-llm-excessive-agency | Always if any tools/function-calling detected; skip (note why) for a pure completion/no-tools app - excessive agency has nothing to evaluate without tool access |
| audit-llm-resource-limits | Always |
| audit-llm-data-privacy-and-isolation | Always |
| audit-llm-supply-chain | Always |
| audit-llm-code-execution-and-multi-agent | Only if a code-execution tool OR multi-agent coordination is detected (per its own applicability check - still worth invoking so it can confirm and report not-applicable formally) |
| audit-llm-output-quality | Always |
| audit-llm-intent-grounding-and-adaptability | Always if the app is agentic (tool-calling/multi-step); for a single-turn completion-only app, run a reduced pass (ambiguity handling and honest limitations still apply; capability-discovery checks don't) |
| audit-llm-prompt-and-context-engineering | Always |
| audit-llm-evals-and-red-teaming | Always |
| audit-llm-observability-and-cost | Always |

"Security-relevant subset" (for the scope question in step 2): prompt-injection,
jailbreak-resistance, guardrails, excessive-agency, data-privacy-and-isolation,
supply-chain, code-execution-and-multi-agent.
