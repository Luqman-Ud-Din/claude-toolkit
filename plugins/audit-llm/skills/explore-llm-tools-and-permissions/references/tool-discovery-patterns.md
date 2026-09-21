# Tool discovery patterns by framework

| Framework | Registration pattern to grep for |
|---|---|
| LangChain | `@tool`, `Tool(name=`, `StructuredTool.from_function(` |
| OpenAI SDK (raw) | `"type": "function"` in a `tools=[...]` list, `FunctionDeclaration` |
| OpenAI Agents SDK | `@function_tool`, `Agent(tools=[` |
| Semantic Kernel | `[KernelFunction]`, `plugins.Add*Plugin(` |
| AutoGen | `register_function(`, `FunctionTool(` |
| CrewAI | `@tool`, `Agent(tools=[` |
| MCP (any host) | server manifest / `tools/list` handler; each connected MCP server is itself a tool source outside this repo - note it as external and check `audit-llm-supply-chain` for that server's provenance |
| Raw HTTP/hand-rolled | a dispatch table or `if tool_name == "..."` chain mapping model output to a function call - grep for the dispatch switch itself when no framework decorator exists |

A tool loaded from a plugin directory or config file at runtime (rather than
declared in source) should be flagged as dynamically registered - list what
you can find in the loading code, but say explicitly that the actual runtime
tool surface may exceed what's visible in source alone.
