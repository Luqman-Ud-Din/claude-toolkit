---
name: explore-llm-tools-and-permissions
description: Catalogs every tool/function the model can call in an LLM or agentic application - its schema, what system or data it touches, which credentials it runs with, whether it reads or writes, and whether the action is reversible and requires human approval - and writes audit/llm/explore/explore-llm-tools-and-permissions.json. Use it whenever the user asks what actions an AI agent can take, wants a list of tools/functions available to a model, asks which tools are dangerous or irreversible, or asks about agent permissions and credential scope - even when the user does not name this skill. Feeds audit-llm-excessive-agency directly and is the primary input propose-llm-controls uses for approval-gate design.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-llm:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Explore: LLM tools and permissions

The single most consequential map in the suite - most agentic-application
harm flows through a tool call, not through the model saying something bad.
Produces a map; whether a permission gap is acceptable is
`audit-llm-excessive-agency`'s call, not this skill's.

Prerequisites: `shared-llm-stack-detection`, `shared-llm-context-bootstrap`,
`shared-llm-handoff-contract`.

## Workflow

1. **Enumerate every tool/function** the model can invoke: framework tool
   decorators (`@tool`, `@function_tool`), manually-built function-calling
   schemas passed to the API, MCP servers/tools the agent connects to, and
   any tool registered dynamically (loaded from config/plugin directory) -
   dynamic registration is itself worth a note, since it means the tool
   surface can change without a code review.
2. **For each tool, record:**
   - **Schema** - parameter names/types as the model sees them. A parameter
     the model fully controls (e.g. a free-form `amount` with no server-side
     cap) is a different risk than one constrained to an enum the caller
     validates.
   - **What it touches** - which system, database, or external API.
   - **Credentials used** - is it the acting user's own scoped credential, or
     a shared service-role credential with broader access than any one user
     should have? A tool that always runs with an elevated service credential
     regardless of who's chatting is a common source of confused-deputy
     findings.
   - **Read or write** - and if write, whether it's additive (create), mutable
     (update), or destructive (delete, send, pay, publish).
   - **Reversibility** - can a human undo this after the fact with no data or
     real-world loss (read, most creates) or not (a sent email, a completed
     payment, a deleted record with no soft-delete, a message posted
     publicly)?
   - **Approval today** - does anything in the code path require a human
     confirmation, a second factor, or a review step before this executes, or
     does the model's decision alone trigger it?
3. **Cross-reference with the language-stack audit** where relevant - a tool
   that runs a raw SQL query built from model output touches
   `audit-injection-vulnerabilities` territory too; note the overlap rather
   than silently duplicating that skill's job.
4. **Write the map** with `items[].detail` shaped as:

   ```json
   {
     "name": "refund_order",
     "schema": {"order_id": "string", "amount": "number"},
     "touches": ["payments DB", "Stripe refund API"],
     "credentials": "service-role Stripe key (full account scope)",
     "operation": "write-destructive",
     "reversible": false,
     "approval_required": false,
     "location": "src/agent/tools/refund_order.py:1"
   }
   ```

5. **Flag the highest-risk tools first** in your summary - a reviewer reading
   only the top of your report should immediately see which tools are
   irreversible and ungated.

## Bundled files

- `references/tool-discovery-patterns.md` - where tool registration lives per framework (LangChain `@tool`, OpenAI function-calling schemas, MCP server manifests, Semantic Kernel `[KernelFunction]`, AutoGen/CrewAI tool lists).
