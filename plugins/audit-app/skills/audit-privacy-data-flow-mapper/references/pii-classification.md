# PII classification

The scanner (`scripts/pii_scan.py`) assigns one class per canonical field. Which
names and values count as personal data is decided by `audit-sensitive-data-catalog`
(`$AUDIT_CORE_ROOT/skills/audit-sensitive-data-catalog/references/catalog.json`): the scanner keeps the catalog's
personal-data canonical fields and uses the catalog `category` as the class (`tier: adjacent`
becomes `pii-adjacent`). Use this file to re-classify by hand when the name is ambiguous, and
to decide what the GDPR skill will treat as special category. Add missing names or formats to
the catalog, never to the scanner.

## Classes

| Class | Meaning | Canonical fields the scanner emits | GDPR note |
|---|---|---|---|
| `identifier` | Identifies a natural person directly or by linkage | `date_of_birth`, `national_id` (SSN, CNIC, Iqama, passport, tax id, driving licence), `ip_address`, `device_id`, `geolocation` | Art.4(1); national ids are often regulated further by national law (Art.87) |
| `contact` | How to reach the person | `email`, `phone`, `first_name`, `last_name`, `full_name`, `address`, `postal_code` | Direct marketing rules (Art.21, ePrivacy) apply to email/phone |
| `financial` | Money and payment instruments | `iban`, `card_number`, `card_security`, `salary` | PCI DSS for card data; card security codes must never be stored |
| `health` | Physical/mental health, care | `health` (diagnosis, prescription, blood group, allergies, disability) | Special category, Art.9 |
| `special-category` | Art.9 data other than health | `special_category` (religion, ethnicity, sexual orientation, political opinion, union membership, biometric, genetic, criminal record Art.10) | Requires an Art.9(2) condition; a finding anywhere outside the model |
| `credential` | Secrets that authenticate the person | `password` (and security answers) | Not "PII" in the marketing sense but always High when logged/cached |
| `pii-adjacent` | Personal but low sensitivity alone; sensitive in combination | `gender`, `age`, `signature`, `photo` | Photo of a face can be biometric if used for recognition |

## Field-name matching rules

Matching is done by `audit-sensitive-data-catalog` (`find_names`, `classify_name`). What
that means for the inventory:

- Identifiers are split on `snake_case`, `camelCase`, `PascalCase` and `kebab-case`, so
  `EmailAddress`, `email_address`, `customerEmail` and `Model.FirstName` all map to their
  canonical field.
- `name` alone is **not** matched (ProductName, TableName); qualified person names are.
- Bare `address` is inventoried as `address`. `ipAddress`, `macAddress` and `emailAddress`
  resolve to `ip_address`, `device_id` and `email`.
- A name followed by a metadata, structural or reference word is not personal data
  (`emailSent`, `emailTemplate`, `dobExpiry`, `address_id`), nor is one after a boolean
  prefix (`hasPassword`, `forgotPassword`). The catalog's `excluded.reason` says why.
- Password hashes and salts keep canonical `password` (form `hashed`), so hashed credential
  columns are inventoried under one field. API keys, tokens, sessions and cookies have no
  canonical field and stay out of the inventory.
- `id` alone is never PII in this scanner; `user_id`/`customer_id` are
  pseudonymous keys and are deliberately not inventoried. Mention them in the
  report only when they are the *only* thing logged (that is the good pattern).
- Short forms such as `age` must stand alone between delimiters (`user_age`, not
  `usage`); still confirm by hand.

## Value patterns

Values come from `audit-sensitive-data-catalog` (`find_values`). The scanner keeps a match
when its canonical field is personal data, it is not a placeholder, and its confidence is
not `low`:

| Value | Catalog behaviour | Where it matters |
|---|---|---|
| Email literal | example domains and fixture mailboxes are placeholders and skipped; asset names such as `logo@2x.png` are rejected | seeds, fixtures, templates, hard-coded recipients |
| Generic mailbox | `support@`, `noreply@`, `info@` on a real domain are tagged `value-generic`; company mailbox, not a data subject - do not inventory | templates, config |
| IBAN | IBAN shape; a failed mod-97 check makes it not sensitive | fixtures, test data, config |
| Card PAN | Luhn-valid card numbers; published test cards are placeholders | fixtures; any real PAN in the repo is a Critical finding regardless of sink |
| National ids | US SSN, PK CNIC, GB NINO, checksum-valid IN Aadhaar; phones and Saudi ids are low confidence and not inventoried | fixtures |

Real PII values in the repository (not placeholders) are a finding in their own
right ("personal data committed to source control"), separate from the flow map.

## Classifying ambiguous names

| Name | Decide by | Usually |
|---|---|---|
| `Name` on `Customer`/`Supplier`/`Contact` | is the entity a natural person or a company? sole traders are persons | contact (say "may be a company name") |
| `Email` on `Company`/`Branch` | a shared mailbox is not personal data; a named person's is | contact, note the ambiguity |
| `Phone` on `Branch` | landline of a shop vs a manager's mobile | pii-adjacent unless it is a mobile |
| `Address` on `Order` (shipping) | belongs to a person | contact |
| `CreatedBy`/`ModifiedBy` (user id or name?) | id -> not inventoried; name/email -> contact | check the type |
| `Notes`/`Remarks`/`Description` free text | can hold anything, including health or complaints | flag as "free text - may contain PII" in the report, do not inventory |
| `Signature` image on invoices | handwriting is personal data; not biometric unless used for authentication | pii-adjacent |
| `Photo`/`Avatar` | personal data; biometric only if face-matched | pii-adjacent (say so) |
| `Cnic`/`Iqama`/`NTN` | national identifiers (Pakistan / Saudi) | identifier |
| `DateOfBirth` used only for age gating | still identifier; consider storing age band | identifier |

## What is NOT inventoried

- Application secrets and API keys (belong to `audit-secrets-and-config`).
- Company/branch master data unless it names a person.
- Aggregated or anonymised statistics.
- Log lines that carry only ids - list them as the good example.
