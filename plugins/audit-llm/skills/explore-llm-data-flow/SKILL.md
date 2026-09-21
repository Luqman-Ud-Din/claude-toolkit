---
name: explore-llm-data-flow
description: Traces everything entering and leaving an LLM application's context window - retrieved documents, tool outputs, memory, vector-store content, user input - and what gets sent out to which model provider, labeling each source's trust tier, and writes audit/llm/explore/explore-llm-data-flow.json. Use it whenever the user asks what data reaches the model, what gets sent to an external AI provider, wants a RAG/retrieval data-flow diagram, asks about PII or secrets ending up in prompts, or asks which data sources feed an agent's context - even when the user does not name this skill. Feeds audit-llm-prompt-injection and audit-llm-data-privacy-and-isolation directly.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-llm:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Explore: LLM data flow

Two directions matter equally: what flows **in** to the context window
(everything that can influence the model) and what flows **out** to a
provider (everything that leaves the organization's control). Produces a
map; trust verdicts use `shared-llm-trust-classification` so every consumer
agrees on them.

Prerequisites: `shared-llm-stack-detection`, `shared-llm-context-bootstrap`,
`shared-llm-trust-classification`, `shared-llm-handoff-contract`.

## Workflow

1. **Inbound sources.** For every place content joins the context window
   (system prompt variables already covered by `explore-llm-prompts` - link
   to it rather than re-tracing - plus retrieval results, tool/API call
   results, uploaded files/images, memory reads, other agents' messages),
   classify with `shared-llm-trust-classification` and record where in the
   prompt/message structure it lands (a separate tool-result message role,
   or spliced into free text with no delimiter - the latter is worth flagging
   for `audit-llm-prompt-injection`).
2. **Outbound destinations.** For every call that leaves the process boundary
   to a model provider, record which provider, what's included in the
   request (the full conversation history? retrieved chunks? file contents?),
   and whether anything looks like it shouldn't leave the org: secrets,
   credentials, unredacted PII, or another tenant's data appearing in a
   request built for a different tenant.
3. **Vector stores and memory specifically.** Note the isolation boundary -
   is retrieval/memory scoped by tenant/user at the query level (a `WHERE
   tenant_id = ?` filter or a per-tenant index/namespace), or is scoping only
   enforced by what gets indexed in the first place (fragile - a future
   ingestion bug leaks across tenants with no query-time backstop)? This is
   exactly what `audit-llm-data-privacy-and-isolation` needs precisely
   located.
4. **Write the map** with `items[].detail` shaped as:

   ```json
   {
     "direction": "inbound",
     "source": "vector-store retrieval (pgvector, 'kb_chunks' table)",
     "trust_tier": "untrusted",
     "lands_in": "separate tool-result message (delimited)",
     "isolation": "query-time filter on tenant_id",
     "location": "src/rag/retriever.py:30"
   }
   ```

5. **Say what you couldn't trace.** If a request is built by a framework's
   internals in a way you can't fully inspect (an opaque SDK call), say so
   rather than asserting what's included.

## Bundled files

- `references/data-flow-checklist.md` - the specific things to look for at each inbound/outbound point, organized as a checklist.
