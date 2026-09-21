# Assembled inventory report structure

```markdown
# LLM Application Inventory - <app/feature name>

## What it is
One paragraph: purpose, who uses it, single- or multi-agent.

## Architecture
Summary from explore-llm-architecture: entry points, loop control, termination, state.

## Prompts
Summary from explore-llm-prompts: how many, where, which carry untrusted-variable injection risk.

## Tools & permissions
Summary from explore-llm-tools-and-permissions, riskiest first: irreversible + ungated tools named explicitly.

## Data flow
Summary from explore-llm-data-flow: untrusted inbound sources, outbound destinations, any isolation gaps.

## Behavioral baseline
(if gathered) Summary from explore-llm-behavior: notable answered/refused/fabricated/stated_limitation patterns.

## Cross-cutting observations
Anything visible only by reading the maps together - e.g. a tool whose input comes from an untrusted data-flow source.

## Suggested next steps
Which audit-llm-* skills would benefit most from this map, and any open_questions the child skills could not resolve.
```
