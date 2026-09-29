# Changelog

## 0.1.1 - 2026-09-29

- Align shared-llm-stack-detection's skip list with audit-code-scan's repo_walk; it no longer reads build output or the audit workspace's own results.
- Use the MANIFEST_NAMES constant in the manifest walk and drop a glob entry that could never match by set membership.

## 0.1.0 - 2026-09-21

- Initial marketplace packaging of existing skills, including supporting files and eval fixtures.
- Preserve skill IDs and audit output paths; use plugin namespaces for invocation.
- Resolve shared scripts through the audit-core plugin.
