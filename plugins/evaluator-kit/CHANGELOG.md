# Changelog

## 0.1.0 - 2026-10-09

- Initial marketplace packaging of expectations-analysis and submission-audit, including supporting files and eval fixtures.
- expectations-analysis accepts messages and chat histories as input and produces one seven-section Evaluator Lens: description with references, context understanding, evaluator intent, explicit and implicit requirements (reference, impact, severity; implicit with confidence), AI receptiveness, and understanding (matrix, deal breakers, deal makers, submission package). No length cap.
- The handoff folder is docs/evaluator-expectations/ (expectations.md and brief.md; context now lives in the Lens) alongside docs/submission-audit/; the audit reads the new section names.
- Preserve bare skill IDs in handoff files and output paths; use plugin namespaces for invocation.
