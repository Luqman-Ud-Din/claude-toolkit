# data-inventory.json schema

Written by `scripts/pii_scan.py` to
`audit/evidence/audit-privacy-data-flow-mapper/data-inventory.json`. Consumed by
`audit-gdpr-data-protection` (inventory table, rights checks, processors) and
`audit-soc2-controls-evidence` (C1 confidentiality, P1 privacy evidence). Do not
rename top-level keys; add new ones instead.

```json
{
  "skill": "audit-privacy-data-flow-mapper",
  "generated_at": "2026-09-11T10:00:00Z",
  "root": "D:/repo",
  "files_scanned": 812,
  "fields": [
    {
      "field": "email",
      "classification": "contact",
      "aliases": ["Email", "EmailAddress", "email_address"],
      "storage": [
        {"type": "table", "name": "Customer", "file": "Entities/Customer.cs", "line": 11},
        {"type": "cache", "name": "cache/redis", "file": "Services/CustomerService.cs", "line": 37}
      ],
      "collection_points": [
        {"type": "dto", "name": "CustomerRequest", "file": "HostModel/CustomerRequest.cs", "line": 7},
        {"type": "handler", "dto": "CustomerRequest", "file": "Controllers/CustomersController.cs", "line": 17}
      ],
      "processors": [
        {"type": "log", "file": "Services/CustomerService.cs", "line": 35, "snippet": "...", "third_parties": []},
        {"type": "cache", "file": "Services/CustomerService.cs", "line": 37, "snippet": "..."},
        {"type": "outbound", "file": "Services/CustomerService.cs", "line": 39, "snippet": "...", "third_parties": ["Mailchimp"]},
        {"type": "template", "file": "Templates/Emails/Welcome.cshtml", "line": 5, "snippet": "..."}
      ],
      "third_parties": [{"name": "Mailchimp", "via": "outbound", "file": "Services/CustomerService.cs", "line": 39}],
      "retention": "unknown - no retention/purge job found in code",
      "occurrence_count": 7,
      "occurrences": [
        {"field": "email", "classification": "contact", "matched_by": "name|value|value-generic",
         "context": "line|lookahead:41", "sink": "log", "file": "...", "line": 35, "snippet": "...",
         "container": null, "third_parties": [], "protected": false}
      ]
    }
  ],
  "third_parties": [
    {"name": "Mailchimp", "category": "marketing", "files": ["Services/CustomerService.cs", "appsettings.json"],
     "fields": ["email", "first_name", "last_name"], "dpa": "unknown - organisational"}
  ],
  "unresolved_hosts": {"api.partner.example": ["Services/PartnerSync.cs"]},
  "retention_hints": [{"file": "Jobs/PurgeJob.cs", "line": 20, "snippet": "older_than ..."}],
  "flows": [
    {"field": "email", "from": "collection", "to": "table:Customer", "via": "write"},
    {"field": "email", "from": "table:Customer", "to": "proc:log", "via": "log"},
    {"field": "email", "from": "table:Customer", "to": "vendor:Mailchimp", "via": "http"}
  ],
  "stats": {"fields": 5, "occurrences": 20, "by_sink": {"model": 5, "log": 1, "...": 0}, "by_classification": {"contact": 4}},
  "not_checked": [{"item": "retention", "reason": "..."}]
}
```

## Field rules

- `field`: canonical field from `audit-sensitive-data-catalog` (classes in `references/pii-classification.md`); one entry per
  canonical field across the whole repo (aliases hold the spellings seen).
- `classification`: `identifier | contact | financial | health | special-category | credential | pii-adjacent`.
- `storage[].type`: `table` (entity/schema; `name` = class or table), `model`
  (class not confirmed as persisted), `cache`, plus values the manual pass adds:
  `file-store`, `backup`, `export`, `browser-storage`, `queue`.
- `processors[].type`: `log | cache | analytics | template | messaging | outbound | url`.
  `outbound`, `messaging` and `analytics` carry `third_parties`.
- `sink` values in occurrences: the processor types plus `model | schema | dto | collection | code`.
  `code` = a reference that is not a flow edge (assignment, mapping, validation).
- `context`: `line` when the sink was on the same line; `lookahead:N` when the
  line feeds a call on line N (payload builders).
- `protected`: true if the same line hashes/masks/encrypts the value; the manual
  pass must confirm before treating it as pseudonymised.
- `retention`: free text; the scanner only writes "unknown - ..." variants. The
  manual pass replaces it with the TTL / job / policy found, or leaves it.
- `flows`: edges for the diagram; `from`/`to` are `collection`, `table:<name>`,
  `proc:<type>`, `vendor:<name>`.

## How the manual pass edits it

Edit the copy under `audit/evidence/...` (never the audited code): add storage
locations the scanner cannot see (backups, S3 buckets, Drive folders, reports),
set `retention` where a job or TTL was found, add `dpa`/`region` to third
parties when known, and append to `not_checked`. Keep the file valid JSON -
`python -c "import json; json.load(open('data-inventory.json'))"`.

## How consumers read it

- GDPR skill: `fields[]` -> inventory table; `third_parties[]` -> processor list
  (Art.28/30); `processors[].type == "log"|"url"|"analytics"` -> minimisation
  findings (Art.5(1)(c)); `storage[]` -> erasure/portability coverage;
  `retention` -> Art.5(1)(e).
- SOC 2 skill: `third_parties[]` -> vendor management evidence (CC9.2);
  `fields[].classification` -> data classification evidence (C1.1);
  `processors[].type == "log"` -> confidentiality of logs (C1.1, CC7.2).
