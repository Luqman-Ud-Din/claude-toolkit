# Changelog

## 0.1.1 - 2026-09-29

- Fix double-encoded middot in the generated README plugin index.
- Validate that each plugin's version matches between marketplace.json and plugin.json.
- Reuse audit-findings-rollup's severity list in audit-report-generator and audit-owasp-asvs-mapper instead of re-declaring it.
- Align audit-stack-detection's skip list with audit-code-scan's repo_walk so the stack is detected from the files the audits read.
- Remove an unreachable helper and a now-unused import in audit-endpoint-inventory.
- Correct the self-negating plugin-invocation note in all nine audit-core skills.

## 0.1.0 - 2026-09-21

- Initial marketplace packaging of existing skills, including supporting files and eval fixtures.
- Preserve skill IDs and audit output paths; use plugin namespaces for invocation.
