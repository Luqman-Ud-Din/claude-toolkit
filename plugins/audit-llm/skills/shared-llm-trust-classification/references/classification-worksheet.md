# Trust classification worksheet

Fill one row per distinct source found while tracing data flow into the
context window. Reuse this table's `id` values as the `location`/`id` fields
in `explore-llm-data-flow`'s output so downstream skills can join on them.

| id | Source | Tier | Justification | Reaches which prompt/tool |
|---|---|---|---|---|
| sys-prompt | Hard-coded system prompt template | Trusted | Developer-authored, deployed via CI, no runtime user input | main agent system message |
| user-msg | Authenticated user's chat message | Semi-trusted | Comes from the logged-in session, but attacker-controlled content within it | main agent user turn |
| rag-chunk | Vector-store retrieval result | Untrusted | Indexed from documents that may include third-party or historical content the current user didn't author | injected into user turn as context block |
| tool-out-search | Web search tool result | Untrusted | Arbitrary third-party web content | tool result message |
| memory-profile | Stored user preference memory | Semi-trusted (if scoped) / Untrusted (if cross-tenant writable) | Depends on whether write access is restricted to the same authenticated user | system prompt splice - flag if so |
| agent-msg-b | Message from Agent B in a multi-agent pipeline | Untrusted (unless authenticated) | No signature/auth on inter-agent messages found | Agent A's context |

Example justification for an untrusted verdict that a naive reviewer might
mislabel as trusted: "the RAG index is built from our own product docs, so
it's trusted" - it's still untrusted, because anyone who can get content into
that index (a support ticket importer, a public wiki sync, a scraped page)
can get instructions into the model's context. Trust follows who can write to
the source at any point in its lifecycle, not who currently owns the pipeline.
