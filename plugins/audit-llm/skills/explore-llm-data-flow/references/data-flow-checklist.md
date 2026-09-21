# Data flow checklist

## Inbound

- [ ] Every retrieval call: what's the query, what's the source index/table, is it filtered by tenant/user at query time?
- [ ] Every tool result: does it land in a distinct message role/tag, or get string-concatenated into the next prompt?
- [ ] File/image uploads: is extracted text/OCR treated as untrusted per `shared-llm-trust-classification`?
- [ ] Memory reads: scoped to the reading user/tenant, or globally readable?
- [ ] Inter-agent messages (if multi-agent): authenticated sender, or any agent can claim to be any other?

## Outbound

- [ ] Which provider(s) receive requests, and under what data-processing agreement (note if unknown - that's a question for `audit-llm-supply-chain`/`audit-llm-data-privacy-and-isolation`, not something to guess).
- [ ] Does the outbound payload include full conversation history, or a trimmed/summarized window? A growing history is also relevant to `audit-llm-resource-limits`.
- [ ] Any field that looks like a secret, credential, or raw PII making it into a logged or provider-bound payload?
- [ ] Multi-tenant apps: any code path where one tenant's retrieved/cached content could end up in a request built for another tenant's session?
