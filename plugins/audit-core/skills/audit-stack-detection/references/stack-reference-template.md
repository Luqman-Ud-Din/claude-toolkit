# <Stack name> reference for <skill-name>

Copy this file to `<consumer-skill>/references/<stack-id>.md` to add a stack to an
audit skill. The stack id must be one listed in `stack-json-contract.md`. Keep the
same section headings so the consumer's SKILL.md workflow can point at them by name.
Every section should answer "where do I look, what does bad look like, what does good
look like" for this stack only; cross-stack reasoning belongs in the consumer's SKILL.md.

## Stack markers

How `detect_stack.py` (or `audit/stack.json`) identifies this stack, and
any sub-variants worth distinguishing (for example minimal APIs vs controllers,
class components vs hooks).

## Where the relevant code lives

Typical folders, file suffixes, naming conventions, and framework entry points
to open first.

## Dangerous / interesting APIs and patterns

Bullet list of concrete API names, decorators, annotations, config keys, and
code shapes the automated pass should grep for. Mirror these in the consumer's
`scripts/patterns/<stack-id>.json` (format owned by `audit-code-scan`) so the grep
pass and the manual pass agree.

## What "good" looks like

The idiomatic secure/correct pattern for this stack, with a short code example
the remediation text can point to.

## Manual trace checklist

The highest-risk flows to trace by hand after the automated pass, in priority
order, and what evidence proves each one safe.

## Stack-specific false positives

Hits the grep pass will produce that are usually fine in this stack, and how to
confirm they are fine.

## Tooling

Analyzers, linters, scanners, or CLI commands available for this stack that can
strengthen the automated pass, with the exact invocation.

## References

Framework docs, OWASP cheat sheets, ASVS sections, CWE ids most relevant to
this stack.
