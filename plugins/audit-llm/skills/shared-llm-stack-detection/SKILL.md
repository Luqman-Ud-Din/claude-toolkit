---
name: shared-llm-stack-detection
description: Detects LLM SDKs (openai, anthropic, google-genai, mistralai, cohere, ollama, bedrock), agent frameworks (langchain, langgraph, llama-index, autogen, crewai, semantic-kernel, pydantic-ai, OpenAI Agents SDK, langchain4j, Spring AI), vector stores (pinecone, weaviate, chroma, qdrant, pgvector, milvus, faiss), and guardrail libraries (NeMo Guardrails, Guardrails AI, LLM Guard, Llama Guard / Prompt Guard) in a codebase, and writes the shared audit/llm-stack.json that every llm-audit-* skill reads so the LLM stack is detected once. This is a shared building block, not run standalone - it backs explore-llm-application, audit-llm-application, audit-llm-supply-chain, and any llm-audit-* skill invoked without prior explore output. Use it whenever another skill needs to know which LLM SDK, agent framework, vector store, or guardrail library a repo uses, or whenever the user asks what LLM stack an app is built on - even when the user does not name this skill.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-llm:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Shared: LLM stack detection

One job: answer "which LLM SDKs, agent frameworks, vector stores, and guardrail
libraries does this repository use, and where" and record the answer in
`audit/llm-stack.json`. It complements, and runs alongside, `audit-stack-detection`
(the general language/framework detector) rather than replacing it - an audit of
an LLM feature almost always needs both `audit/stack.json` (it's a .NET repo) and
`audit/llm-stack.json` (it calls the Anthropic SDK via LangChain).

Read-only rule: the audited code is never modified. The only write is
`audit/llm-stack.json`, and only when `--write` is passed.

## Inputs and prerequisites

- A repository root on disk.
- Python 3, standard library only.

## Workflow

1. **Reuse an existing answer.** If `audit/llm-stack.json` exists, the script
   prints it unchanged; pass `--force` to re-detect.
2. **Detect.** Run from the audited repository root:

   ```bash
   python <skills-dir>/shared-llm-stack-detection/scripts/detect_llm_stack.py <repo> [--write] [--force]
   ```

   `<skills-dir>` is the `skills/` folder of the `audit-llm` plugin. From another
   skill in this plugin the path is
   `../shared-llm-stack-detection/scripts/detect_llm_stack.py`, relative to that
   skill's directory.
3. **Sanity-check the result.** Detection is marker-based (manifest dependency
   names and import strings), so confirm before an audit depends on it:
   - A framework like LangChain or Semantic Kernel can wrap more than one
     underlying model provider - list every provider actually configured, not
     just the first one found.
   - Guardrail libraries are often present in the manifest but unused or
     partially wired; note "present" vs "invoked on the request path" and let
     `audit-llm-guardrails` confirm the difference.
   - A repo with no marker hits is not necessarily LLM-free - it may call a
     model over a raw HTTP client with no SDK. Say so rather than reporting
     an empty stack as "not an LLM application".
4. **Hand the answer back.** Report each category (`llm_sdks`, `agent_frameworks`,
   `vector_stores`, `guardrails`), the evidence file for each hit, and whether
   any hit looks like agentic orchestration (multi-step tool-calling loop) versus
   a single completion call - `explore-llm-architecture` needs that distinction.
5. **Say what was not detected.** An SDK or framework outside the marker list
   produces no entry and a warning; add its marker to the script rather than
   guessing at its behavior.

## llm-stack.json contract

```json
{
  "detected_at": "ISO-8601",
  "root": "absolute path",
  "llm_sdks": [{"id": "anthropic", "evidence": ["Api/Api.csproj"], "roots": ["Api"]}],
  "agent_frameworks": [{"id": "langchain", "evidence": ["requirements.txt"], "roots": ["worker"]}],
  "vector_stores": [{"id": "pgvector", "evidence": ["requirements.txt"]}],
  "guardrails": [],
  "likely_agentic": true,
  "notes": ["no marker hit for the /chat service - check for a raw HTTP client call"]
}
```

`likely_agentic` is a hint (a tool-calling or agent-framework marker was found),
not a verdict - `explore-llm-architecture` confirms it by reading the control flow.

## Bundled files

- `scripts/detect_llm_stack.py` - detection; honours an existing `audit/llm-stack.json`.
- `references/llm-stack-markers.md` - the full marker table by category and manifest type, and how to add a new one.
- `evals/` - sample repos: a polyglot repo with LangChain + pgvector, a raw-HTTP-only repo with no SDK markers, and a repo with an existing llm-stack.json.
