# Agent loop shapes by framework

| Framework | Where the loop lives | Where termination is usually configured |
|---|---|---|
| LangGraph | A `StateGraph` with nodes/edges; the loop is graph traversal | Conditional edges routing to `END`, or a `recursion_limit` on the graph invocation |
| AutoGen (autogen-agentchat) | `GroupChat` / `RoundRobinGroupChat` manager | `max_turns` on the chat, or a termination condition object (`TextMentionTermination`, `MaxMessageTermination`) |
| CrewAI | A `Crew`'s `process` (sequential or hierarchical) over `Task`s | Implicit - ends when all tasks complete; a hierarchical manager can loop back, check for a `max_iter` on agents |
| Semantic Kernel | A planner (`FunctionCallingStepwisePlanner` or manual loop) | `maximum_iterations` / `MaxTokens` on the planner options |
| OpenAI Agents SDK | `Runner.run` over an `Agent` with `handoffs`/`tools` | `max_turns` parameter on `Runner.run` |
| Hand-rolled `while` loop | Wherever the loop is written - grep for `while True`, `for _ in range(`, or a recursive tool-calling function | Look for an explicit counter/break; its absence is the finding, not a modeling gap on your part |

A framework being present (per `shared-llm-stack-detection`) does not mean the
app uses its built-in termination controls - many hand-rolled loops sit next
to an unused framework import. Verify the actual call site, not just which
package is installed.
