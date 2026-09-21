# Minimal fallback per explore map

When the map at this path is absent, the recommended narrow fallback is:

| Absent map | Minimal fallback (not the full explore skill) |
|---|---|
| `explore-llm-architecture.json` | Read the top-level entry point / main agent loop file only; identify single- vs multi-agent and the termination condition, skip the full control-flow trace. |
| `explore-llm-prompts.json` | Grep for the system-prompt construction site(s) (`system=`, `SystemMessage`, prompt template files) named by `shared-llm-stack-detection`'s evidence, read only those. |
| `explore-llm-tools-and-permissions.json` | Grep for tool/function-calling registration (`@tool`, `tools=[`, `FunctionDeclaration`, `[McpServerTool]`) and list what's found without classifying reversibility in depth. |
| `explore-llm-data-flow.json` | Identify the retrieval/tool-output injection points only (where external content joins the prompt), skip full trust labeling of every source. |
| `explore-llm-behavior.json` | Skip entirely for a code-only review; only relevant when probing a running app, which `shared-llm-probe-runner` gates anyway. |

A skill using a fallback must say so explicitly in its output ("no prior
explore-llm-prompts map found; located the system prompt via a narrow grep
instead of the full inventory") so the user can ask for the fuller pass if the
narrow one leaves an open question.
