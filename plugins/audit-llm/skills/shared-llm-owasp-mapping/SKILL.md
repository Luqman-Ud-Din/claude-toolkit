---
name: shared-llm-owasp-mapping
description: Reference mapping of the OWASP Top 10 for LLM Applications (2025), the OWASP Top 10 for Agentic Applications (2026), MITRE ATLAS techniques, and NIST AI RMF / AI 600-1 controls onto the 13 llm-audit-* Area values. This is a shared building block, not run standalone - every audit-llm-* skill fills a finding's References field from here, and audit-owasp-asvs-mapper can extend its existing coverage matrix with these ids when a repo is audited with both suites. Use it whenever a skill needs an OWASP LLM/Agentic id, a MITRE ATLAS technique id, or a NIST AI RMF control to cite for an LLM-specific finding, or whenever the user asks which OWASP LLM/Agentic category or ATLAS technique a given LLM risk maps to.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-llm:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Shared: OWASP LLM/Agentic mapping

Keeps every `audit-llm-*` skill citing the same standard ids for the same
Area, instead of each skill picking its own References wording. The full
table is `references/owasp-llm-agentic-mapping.md`; this file is the lookup
procedure.

## Workflow

1. Look up the Area value (from `shared-llm-finding-format`) in
   `references/owasp-llm-agentic-mapping.md`.
2. Cite the OWASP LLM Top 10 id and, where the Area also maps to the Agentic
   Top 10, both ids together (`LLM06:2025 / ASI02:2026`) - both anchors are
   useful to a reader coming from either standard.
3. Add a MITRE ATLAS technique id only when the finding's mechanism actually
   matches a cataloged technique (don't force one) - see the table's ATLAS
   column for common matches per Area.
4. Add a NIST AI RMF function (`Govern`/`Map`/`Measure`/`Manage`) when the
   finding is about a process gap (missing evals, missing monitoring) rather
   than a specific exploitable defect - process gaps map to NIST more
   naturally than to a CWE-style technical id.

## A caveat worth repeating to the user

The OWASP Top 10 for Agentic Applications (2026) is newer and less settled
than the 2025 LLM list; category names and numbering can still shift between
draft revisions. Treat the ASI ids in the mapping table as best-effort and
say so in any report that cites them, and suggest the user cross-check
against the current published revision before treating an ASI id as a fixed
external reference (e.g. in a compliance document).

## Bundled files

- `references/owasp-llm-agentic-mapping.md` - the full mapping table: Area -> OWASP LLM id -> OWASP Agentic id -> representative MITRE ATLAS technique -> NIST AI RMF function.
