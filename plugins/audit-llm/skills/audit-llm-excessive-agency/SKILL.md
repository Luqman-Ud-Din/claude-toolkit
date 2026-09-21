---
name: audit-llm-excessive-agency
description: Evaluates an LLM agent's tool permissions against least privilege - credential scoping, whether irreversible actions have a human approval gate, and whether that approval gate or a read-only mode can be bypassed by the model itself (e.g. by calling a differently-named tool, or by arguing its way past a check meant to stop it). Use it whenever the user asks whether an AI agent has too much power, wants a review of agent tool permissions or approval gates, asks "can the AI actually do X without a human checking", or is deciding whether to grant an agent a new capability - even when the user does not name this skill. Writes findings with Area "Excessive Agency" (prefix EA) to audit/findings/audit-llm-excessive-agency.json.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-llm:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit: LLM excessive agency

OWASP LLM06, ASI02, ASI03. This is usually the highest-impact audit in the
suite for agentic applications - most real-world agent harm is a tool call,
not a bad sentence.

Prerequisites: `shared-llm-context-bootstrap`, `shared-llm-finding-format`,
`audit-finding-writer`.

## Workflow

1. **Bootstrap.** Strongly prefer
   `audit/llm/explore/explore-llm-tools-and-permissions.json` - it already has
   the per-tool schema, credentials, reversibility, and approval data this
   audit needs. Absent, run the narrow fallback (grep tool registrations)
   rather than the full explore skill.
2. **Rank every tool by reversibility × approval gap.** For each tool marked
   irreversible with no approval requirement, this is close to an automatic
   finding - state the specific scenario (what a wrong or manipulated model
   decision would cause) rather than a generic "excessive agency" label.
3. **Check least privilege on credentials.** Does each tool run with a
   credential scoped to only what it needs (the acting user's own permission
   level), or a shared service-role credential broader than any single
   action requires? A confused-deputy pattern - the agent, acting on one
   user's request, but with admin-level backend credentials - is a distinct,
   commonly-missed finding from the missing-approval-gate one; check for both
   even on the same tool.
4. **Verify the approval gate itself can't be bypassed.** An approval step
   is only a real control if:
   - The model cannot skip straight to the action-taking tool while the
     "propose" step exists as a separate, unused tool the model can still
     call directly.
   - The confirmation token/id is generated server-side and can't be guessed
     or forged by constructing a plausible-looking call.
   - A read-only/dry-run mode (if the app has one) is enforced by the server,
     not by the model choosing to respect a flag it was told about in the
     prompt - that's a prompt-only control per `audit-llm-guardrails`'
     enforcement classification; cross-reference it if this audit finds one.
5. **Check for privilege escalation via the agent itself** - can the model be
   asked (directly or via injected content, cross-reference
   `audit-llm-prompt-injection`) to register a new tool, change its own
   permission scope, or call an admin-only capability meant for a different
   role?
6. **Rate and write findings** via `audit-finding-writer`, Area "Excessive
   Agency" / prefix `EA`. This audit is `propose-llm-controls`'s primary
   input - write Remediation with enough concrete detail (the exact
   propose/confirm split, the exact credential to scope down) that a
   proposal can be built directly from it.

## Bundled files

- `references/approval-gate-patterns.md` - concrete propose/confirm and credential-scoping patterns per common tool shape (payment, data deletion, external communication, admin action).
