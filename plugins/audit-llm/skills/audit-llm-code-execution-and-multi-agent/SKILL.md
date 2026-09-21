---
name: audit-llm-code-execution-and-multi-agent
description: Conditional audit that runs only when an LLM application executes model-generated code or coordinates multiple agents - reviews code-execution sandboxing (escape risk, resource limits, network/filesystem access) and the trust, authentication, and integrity of messages passed between agents. Use it whenever the user asks about a code interpreter or sandbox for AI-generated code, sandbox escape risk, multi-agent message trust, agent-to-agent authentication, or "can one agent trick another agent in our pipeline" - even when the user does not name this skill, and skip it entirely (say why) when the app does neither. Writes findings with Area "Code Execution & Multi-Agent" (prefix CE) to audit/findings/audit-llm-code-execution-and-multi-agent.json.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-llm:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit: LLM code execution and multi-agent

OWASP ASI05, ASI07. **Conditional**: check applicability before doing any
work - if the app has no code-execution tool and is single-agent, say so and
stop; don't force findings on a mechanism that isn't present, per design
principle 4's "flag it for the right skill instead of acting on it" (here,
the right answer is "not applicable").

Prerequisites: `shared-llm-context-bootstrap`, `shared-llm-finding-format`,
`audit-finding-writer`.

## Applicability check

1. From `explore-llm-tools-and-permissions` (or a direct grep): is there a
   code-interpreter/execution tool (a Python/JS sandbox, a `run_code` tool,
   an `eval`-style tool)? If yes, run the **Code execution** section.
2. From `explore-llm-architecture`'s agent map (or a direct check): are there
   two or more distinct agents/models that pass messages to each other? If
   yes, run the **Multi-agent** section.
3. If neither applies, report that explicitly and stop - this is the correct,
   complete output for this skill on a single-agent, no-code-execution app.

## Code execution section

- **Sandboxing**: is generated code actually executed in an isolated sandbox
  (container, VM, restricted interpreter) or in the same process as the
  application? Same-process execution of model-generated code is close to an
  automatic Critical finding.
- **Escape surface**: network access, filesystem access outside a scratch
  directory, and ability to spawn subprocesses from inside the sandbox -
  each an escalation path if present.
- **Resource limits on the sandbox itself**: CPU/memory/time caps, separate
  from the agent-level caps `audit-llm-resource-limits` checks - a sandboxed
  process can still be a denial-of-service vector against the host if
  unbounded.
- **Output trust**: is the sandbox's stdout/return value treated as
  untrusted per `shared-llm-trust-classification` before it re-enters the
  model's context (same indirect-injection risk as any other tool output)?

## Multi-agent section

- **Authentication**: can Agent A verify a message actually came from Agent B
  and not from an injected or spoofed source (per `shared-llm-trust-classification`,
  inter-agent messages are untrusted by default unless authenticated)?
- **Message integrity**: is there any tampering protection on the channel
  between agents (signed messages, a trusted broker) or is it a shared
  mutable state / plain message queue any component could write to?
- **Cascading trust**: if Agent A is compromised (via injection elsewhere),
  can it manipulate Agent B into taking an action Agent B alone wouldn't
  have agreed to? Trace at least one concrete cascade scenario.
- **Isolation between agents' credentials**: does each agent hold only the
  credentials its own role needs, or do all agents share one broad
  credential (a multi-agent version of the confused-deputy pattern
  `audit-llm-excessive-agency` checks per-tool)?

## Output

Rate and write findings via `audit-finding-writer`, Area "Code Execution &
Multi-Agent" / prefix `CE`. If neither section applied, write a brief
not-applicable note to `audit/findings/audit-llm-code-execution-and-multi-agent.json`'s
`scope.not_checked` rather than an empty file with no explanation.

## Bundled files

- `references/sandbox-checklist.md` - concrete sandboxing controls to verify for common code-execution setups (subprocess-based, container-based, WASM-based).
