---
name: audit-llm-data-privacy-and-isolation
description: Reviews secrets and PII exposure in LLM context and outputs, what data providers receive and retain, redaction practices, and tenant isolation across vector stores, caches, memory, and conversation state - plus LLM-specific GDPR concerns like erasure from embeddings, caches, and logs. Use it whenever the user asks whether an AI feature leaks data across tenants or users, sends PII to a model provider, retains data too long, or can honor a deletion/erasure request that includes vector embeddings and logs - even when the user does not name this skill. Writes findings with Area "Data Privacy & Isolation" (prefix DP) to audit/findings/audit-llm-data-privacy-and-isolation.json.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-llm:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit: LLM data privacy and isolation

OWASP LLM02, LLM08, ASI06. For a multi-tenant SaaS backend also run
`audit-multi-tenant-isolation`; that skill covers the general application,
this one covers what's specific to the LLM/vector-store surface - overlap is
expected and should be cross-referenced, not duplicated.

Prerequisites: `shared-llm-context-bootstrap`, `shared-llm-trust-classification`,
`shared-llm-finding-format`, `audit-finding-writer`.

## Workflow

1. **Bootstrap.** Prefer `audit/llm/explore/explore-llm-data-flow.json` for
   isolation boundaries already located; absent, trace retrieval/memory
   query paths directly.
2. **Secrets and PII in context.** Check whether prompts, retrieved chunks,
   or logs can carry secrets (API keys, tokens) or PII that shouldn't reach a
   third-party provider or a log sink - cross-reference `audit-secrets-and-config`
   and `audit-logging-and-observability` rather than re-running their full
   scans; add only what's specific to LLM request/response payloads (e.g. a
   full conversation transcript logged verbatim including anything the user
   typed).
3. **Provider data handling.** What does the model provider's terms/data
   processing agreement say about retention and training use of submitted
   data? If unknown, flag as a gap for `audit-llm-supply-chain` /
   organizational follow-up rather than guessing.
4. **Tenant/user isolation on the LLM-specific surface:**
   - Vector store queries filtered by tenant/user at query time, not only at
     ingestion.
   - Memory reads scoped to the reading identity.
   - Prompt caching (if used) keyed in a way that can't serve one user's
     cached response, containing their data, to a different user.
   - Conversation/session state storage scoped correctly (ties back to
     `explore-llm-architecture`'s state-scoping note if available).
5. **GDPR-specific erasure check.** When a user/record is deleted, does
   deletion actually reach: the vector store's embeddings for that user's
   content, any prompt/response logs, any cached responses, and any
   fine-tuning or eval dataset built from their data? An embedding is
   personal data too if it was derived from personal content - deleting the
   source row but leaving the embedding is an incomplete erasure. Cross-reference
   `audit-gdpr-data-protection` for the general erasure-pipeline review;
   add the embedding/vector-store-specific gap here since that skill may not
   know to check it.
6. **Rate and write findings** via `audit-finding-writer`, Area "Data Privacy
   & Isolation" / prefix `DP`.

## Bundled files

- `references/erasure-checklist.md` - every place LLM-application personal data can persist after a "delete my data" request, so erasure claims can be verified store by store.
