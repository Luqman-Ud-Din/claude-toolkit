# LLM stack marker table

Markers live in `scripts/detect_llm_stack.py` as `MARKERS[category][id] = [substrings]`.
A hit is a plain substring match against manifest file text - no parsing, so it
tolerates any manifest format but can false-positive on comments; a human sanity
check (step 3 in SKILL.md) catches that.

## Categories

| Category | ids currently detected |
|---|---|
| `llm_sdks` | openai, anthropic, google-genai, mistralai, cohere, ollama, bedrock, azure-openai |
| `agent_frameworks` | langchain, langgraph, llama-index, autogen, crewai, semantic-kernel, pydantic-ai, openai-agents, langchain4j, spring-ai, haystack |
| `vector_stores` | pinecone, weaviate, chroma, qdrant, pgvector, milvus, faiss |
| `guardrails` | nemo-guardrails, guardrails-ai, llm-guard, rebuff, presidio |

`AGENTIC_HINTS` marks which `agent_frameworks` ids imply a multi-step tool-calling
loop rather than a single completion call - used to seed `likely_agentic`.

## Manifest files scanned

`package.json`, `requirements.txt`, `pyproject.toml`, `Pipfile`, `*.csproj`,
`pom.xml`, `build.gradle[.kts]`, `go.mod`. `node_modules`, `.git`, `bin`, `obj`,
`dist`, `build`, `__pycache__`, `.venv`, `venv` are skipped.

## What a marker hit does not tell you

- Whether the package is actually imported and called on a live code path, vs.
  installed and unused. Cross-check with a grep for the import line before an
  audit finding depends on it.
- Which model (e.g. which Claude or GPT version) is configured - that lives in
  application config or environment variables, not the manifest. Note it as a
  follow-up for `explore-llm-prompts` or `audit-llm-supply-chain`.
- Guardrails present in a dependency file are not necessarily wired into the
  request path - `audit-llm-guardrails` verifies that.

## Adding a new marker

1. Add the package id and its substrings to the right category dict in
   `scripts/detect_llm_stack.py`.
2. Add it to `AGENTIC_HINTS` if the framework itself drives a multi-step loop
   (LangGraph, AutoGen, CrewAI) rather than just wrapping single calls
   (a bare OpenAI/Anthropic SDK is not, by itself, agentic).
3. Add a fixture under `evals/` if the marker text is unusual (e.g. a Go module
   path or a Gradle Kotlin DSL line) so detection is exercised for that syntax.
