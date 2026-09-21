# GDPR article -> technical check mapping

Check ids match `scripts/gdpr_check.py`. "Status rule" says how the script
decides; the manual pass confirms. UK GDPR article numbers are identical.

| Check id | Article(s) | Obligation | What the script looks for | Status rule | Typical finding (severity) |
|---|---|---|---|---|---|
| `right-access` | Art.15, 12 | Subject can obtain confirmation and a copy of their data | self-service routes (`/me`, `/profile`, `/my-data`, `/gdpr`), export symbols, else GET-by-id on a subject resource | self-service/export -> implemented; GET-by-id only -> partial; nothing -> missing | "No self-service access to personal data" (Medium) |
| `right-portability` | Art.20 | Data provided by the subject in a structured, machine-readable format | `export`, `download`, `portab*`, `takeout`, `dsar` in routes/handlers (JS `export` keyword excluded) | any -> implemented; none -> missing | "No data export endpoint or job" (Medium; Low if B2B-only) |
| `right-erasure` | Art.17, 19, 12(3) | Delete/anonymise on request, propagate to recipients, within one month | DELETE routes whose path/file names a subject resource (users, customers, accounts, profiles, me); `anonymi[sz]e`, `erase`, `forget`, `deleteAccount` symbols. DELETE on sessions/tokens/carts/orders is excluded | subject DELETE -> implemented (still confirm scope); symbols only -> partial; nothing -> missing | "No erasure path for <table>" (High); "Erasure does not reach <vendor>/cache/files" (Medium) |
| `right-rectification` | Art.16 | Subject data can be corrected | PUT/PATCH on a subject resource | any -> implemented | "No way to correct <field>" (Low) |
| `right-restriction-objection` | Art.18, 21 | Restrict processing / object (incl. direct marketing opt-out) | `opt_out`, `unsubscribe`, `do_not_contact`, `suppression`, `restrict_processing` | any -> implemented; none -> missing | "No opt-out flag honoured by marketing sends" (Medium) |
| `consent-capture` | Art.7(1), 4(11), 6(1)(a) | Demonstrate consent: who, when, to what, how | consent/opt-in fields in models; sibling `*At/_at/Date` and `*Version/PolicyId` and `*Source/Ip` fields; pre-checked defaults | ts + version -> implemented; one -> partial; boolean only -> partial (finding); no field -> missing (may be another lawful basis - organisational) | "Consent stored as a bare boolean" (Medium; High if marketing depends on it) |
| `consent-withdrawal` | Art.7(3) | Withdrawal as easy as giving; downstream use stops | `withdraw`, `revoke_consent`, `opt_out`, `unsubscribe` routes/handlers | any -> implemented; consent field but no path -> missing | "No consent withdrawal path" (Medium) |
| `retention-enforcement` | Art.5(1)(e) | Keep no longer than necessary | scheduler markers (Hangfire, @Scheduled, cron, Celery beat, management commands) together with purge/expiry/anonymise logic; TTLs | purge inside job code -> implemented; both present separately -> partial; TTL only -> partial; nothing -> missing | "No retention job for <tables>; logs/backups unbounded" (Medium) |
| `minimisation-logs-urls-analytics` | Art.5(1)(c), 25, 32 | Only necessary data; no leakage into logs, URLs, error trackers, analytics | inventory processors of type log/url/analytics (direct occurrences); grep of log calls with a personal-data name from `audit-sensitive-data-catalog`s, analytics `identify`/`track` blocks, PII route params | any -> missing (finding); none -> implemented (if inventory loaded) | "Email written to logs" (High if shipped off-host); "Email sent to Segment traits" (Medium/High) |
| `encryption-transit` | Art.32 | TLS everywhere | HTTPS redirect/HSTS, `sslmode=require`, `Encrypt=True`; weak: `ssl: false`, `Encrypt=False`, `TrustServerCertificate=True`, `verify=False`, `http://` vendor URLs | markers and no weak -> implemented; weak present -> partial; nothing -> not-checked (infra) | "Database connection without TLS" (Medium) |
| `encryption-at-rest-pseudonymisation` | Art.32(1)(a), 25, 4(5) | Encryption / pseudonymisation where appropriate | field encryption converters, Always Encrypted, pgcrypto, KMS/Key Vault, DataProtection; hashing (bcrypt/argon2) for passwords | field encryption -> partial (disk still infra); hashing only -> partial; nothing -> not-checked | "National id stored in clear" (Medium); "Passwords hashed with MD5/SHA1" (High - hand to secrets skill) |
| `access-logging-pii` | Art.30, 32, 5(2) | Accountability: who accessed/changed what | audit log tables, temporal tables, Envers/@Audited, django-auditlog/simple_history, EntitySubscriber | any -> implemented (confirm reads, not just writes); none -> missing | "No audit trail for PII access" (Medium) |
| `processors-transfers` | Art.28, 30, 44-46 | Processor contracts, records, transfer mechanism | inventory `third_parties`; region hints (`us1`, `us-east-1`) in hosts | processors found -> partial (contracts organisational); none -> implemented/not-checked | organisational list entries; "Undeclared processor <vendor>" (Medium) if the team's list lacks it |
| `breach-detection` | Art.33, 34, 32(1)(b) | Detect, log and notify within 72h | security-event logging (failed login, lockout, role change), central log shipping, alerting hooks | all three -> implemented; some -> partial; none -> missing | "No security event logging/alerting" (Medium) |
| `privacy-by-design` | Art.25, 35 | Privacy considered at design time; DPIA for high risk | PRIVACY/DPIA docs, PR template mentioning privacy, `dpia` symbols | doc/template -> implemented; mentions -> partial; nothing -> missing | organisational item; Info finding pointing at the PR template |

## Articles with no code check (organisational only)

Art.6 lawful basis, Art.9 special-category conditions (the inventory flags the
data; the basis is a decision), Art.13/14 privacy notices (content), Art.27 EU
representative, Art.37-39 DPO, Art.36 prior consultation, Art.40-43 codes and
certification. List them under *Outside code scope* when relevant.

## Severity guidance specific to this skill

- Regulated-data adjustment from the shared rubric applies to everything here:
  move up one when special-category or financial data is involved.
- Absence findings (`location.file` = `.` or the router file) are `confirmed`
  when the script found no route *and* the manual pass searched the obvious
  names; otherwise `likely`.
- Do not stack: "no erasure", "no export", "no withdrawal" are three findings;
  "email in logs in 12 places" is one finding with 12 locations.
- Never rate organisational items; they are not findings.

## Evidence to copy into `audit/evidence/audit-gdpr-data-protection/`

Consent model file(s), the route table (or a grep of route decorators), the
deletion handler(s), scheduled-job registrations, logging configuration,
`gdpr-checks.json`, `rights-matrix.md`, and the inventory the run used.
