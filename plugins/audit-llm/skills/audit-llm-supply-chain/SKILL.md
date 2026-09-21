---
name: audit-llm-supply-chain
description: Assesses model provenance and version pinning, third-party tools, MCP servers, plugins, and imported prompts or datasets in an LLM/agentic application, and checks fallback-provider behavior and exposure to unannounced upstream model changes. Use it whenever the user asks about model versioning, pinning a model version, MCP server trust, third-party tool/plugin provenance, what happens if a model provider changes or deprecates a model, or wants a supply-chain review of an AI feature - even when the user does not name this skill. Writes findings with Area "Supply Chain" (prefix SC) to audit/findings/audit-llm-supply-chain.json.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-llm:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit: LLM supply chain

OWASP LLM03, LLM04, ASI04. Overlaps `audit-dependency-vulnerabilities` for
the SDK packages themselves - that skill covers CVEs in the packages; this
one covers the model, prompt, and dataset supply chain those packages don't.

Prerequisites: `shared-llm-stack-detection`, `shared-llm-context-bootstrap`,
`shared-llm-finding-format`, `audit-finding-writer`.

## Workflow

1. **Bootstrap.** Use `shared-llm-stack-detection`'s output for every
   provider/framework/MCP-adjacent dependency in play.
2. **Model version pinning.** Is the model id a fixed version
   (`claude-sonnet-4-5-20250929`) or a floating alias
   (`claude-latest`, `gpt-4o` without a dated snapshot)? A floating alias
   means behavior, safety tuning, and cost can change with no code change and
   no warning - flag it even though it's convenient, and note the trade-off
   (staying current vs. stability) in Remediation rather than treating
   pinning as an unconditional good.
3. **MCP servers and third-party tool plugins.** For each one found by
   `explore-llm-tools-and-permissions` or a direct grep: is it from a known,
   reviewed source, version-pinned, and does the app validate what it
   actually does (its tool list, its described side effects) rather than
   trusting its self-description blindly? An MCP server is effectively
   unreviewed third-party code with tool-calling access - treat it with the
   same scrutiny as a new production dependency, not as configuration.
4. **Imported prompts/datasets.** Any system prompt, few-shot example set, or
   fine-tuning/eval dataset sourced from outside the team (a shared prompt
   library, a public dataset, a vendor template) - is its provenance
   documented, and could it carry an embedded instruction or biased/poisoned
   example that shapes production behavior?
5. **Fallback provider behavior.** If the app falls back to a secondary model
   provider on primary failure, does the fallback have equivalent guardrails
   and system prompt behavior, or does failover silently downgrade safety
   posture (a cheaper/older fallback model with different training and no
   equivalent guardrail wiring)?
6. **Rate and write findings** via `audit-finding-writer`, Area "Supply
   Chain" / prefix `SC`.

## Bundled files

- `references/mcp-and-plugin-review.md` - a checklist for reviewing a third-party MCP server or plugin before it's added to an agent's tool list.
