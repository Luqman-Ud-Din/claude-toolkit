# Changelog

## 0.1.0 - 2026-10-09

- Initial marketplace packaging of expectations-analysis and submission-audit, including supporting files and eval fixtures.
- expectations-analysis accepts messages and chat histories as input and produces one seven-section Evaluator Lens: description with references, context understanding, evaluator intent, explicit and implicit requirements (reference, impact, severity; implicit with confidence), AI receptiveness, and understanding (matrix, deal breakers, deal makers, submission package). No length cap.
- The handoff folder is docs/evaluator-expectations/ (expectations.md and brief.md; context now lives in the Lens) alongside docs/submission-audit/; the audit reads the new section names.
- submission-audit writes one file, docs/submission-audit/audit.md, in every mode (full, partial, re-audit), replacing the five separate files; re-audits read it before overwriting and carry closed gaps forward.
- submission-audit grades against all seven Lens sections: explicit and implicit requirements by severity (implicit ones gate only at Stated/Strong confidence), the submission package, an AI disclosure section against the evaluator's AI receptiveness and the traces, and deal makers; it accepts reply messages and chat responses as submissions and audits them against the whole thread.
- audit.md has nine numbered sections plus a short appendix; every finding carries an ID, an evidence reference into the submission and a Lens reference, and every gap names the findings it comes from. Met requirements are listed by ID only; the duplicate verdict section, scoring-factor column, re-ticked pre-submission checklist, full evidence ledger and raw inventory output are gone.
- Preserve bare skill IDs in handoff files and output paths; use plugin namespaces for invocation.
