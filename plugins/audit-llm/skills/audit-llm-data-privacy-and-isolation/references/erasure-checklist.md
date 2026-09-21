# Where LLM-application personal data can persist

| Store | Check |
|---|---|
| Vector store / embeddings | Embeddings derived from the user's content deleted, not just the source row |
| Prompt/response logs | Conversation transcripts containing the user's messages purged or redacted |
| Response cache | Any cached model response keyed in a way that could still serve the deleted user's content to someone else |
| Memory / long-term profile store | Per-user memory entries deleted |
| Eval/fine-tuning datasets | If the app builds training or eval data from real conversations, the user's contributions removed or the dataset excludes them going forward |
| Provider-side retention | Whether the model provider itself retains the request for any period - outside the app's direct control but worth documenting for the DPA/organizational answer |

An erasure pipeline that deletes the database row but leaves the vector
embedding queryable is incomplete erasure - the embedding can still surface
the deleted content's substance in retrieval results even without the
original text stored locally.
