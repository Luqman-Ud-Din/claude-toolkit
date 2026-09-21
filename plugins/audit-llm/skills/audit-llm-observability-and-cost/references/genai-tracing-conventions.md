# OpenTelemetry GenAI semantic conventions - fields to check for

| Field | What it captures |
|---|---|
| `gen_ai.system` | Provider name (e.g. `anthropic`, `openai`) |
| `gen_ai.request.model` | The exact model id requested |
| `gen_ai.request.max_tokens` / `gen_ai.usage.input_tokens` / `gen_ai.usage.output_tokens` | Token accounting per call |
| `gen_ai.operation.name` | e.g. `chat`, `tool_call` |
| `gen_ai.tool.name` | Which tool was invoked, for a tool-call span |
| span duration | Per-call latency, distinct from end-to-end request latency |

A trace that only has one span for the entire agent run (no per-step
breakdown) can't answer "which step is slow/expensive" - recommend per-call
spans nested under the run, not just a single wrapping span, when that
granularity is missing.
