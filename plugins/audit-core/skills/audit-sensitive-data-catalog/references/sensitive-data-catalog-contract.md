# Sensitive-data catalog contract

Owned by `audit-sensitive-data-catalog`. Consumer scripts code against this file,
not against the internals of `scripts/catalog.py` or the layout of individual rules.

Contract version: **1.0** (printed as `contract` in every CLI document).
Catalog data version: `version` in `references/catalog.json` (printed as `catalog_version`).

## Loading

```python
import importlib.util, os
_CAT = os.path.join(_SKILLS, "audit-sensitive-data-catalog", "scripts", "catalog.py")
_spec = importlib.util.spec_from_file_location("sensitive_data_catalog", _CAT)
sdc = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(sdc)
```

Load by path under a unique module name. Several skills ship a `catalog.py`, so a bare
import can pick up the wrong one. Every function below loads the default catalog
lazily. Pass `catalog=sdc.load(path)` to use another file (tests, a customised fork).

## Functions

| Function | Returns |
|---|---|
| `load(path=None)` | `Catalog` object. Raises `ValueError` on an unknown category or a form listed in two rules with overlapping contexts. |
| `classify_name(identifier, context="any", catalog=None)` | name result dict (below) |
| `find_names(text, context="any", catalog=None, sensitive_only=True)` | list of name result dicts, each with `start` and `end` offsets into `text` |
| `find_values(text, catalog=None, rules=None, dedupe=True)` | list of value match dicts sorted by `start`. `rules` limits to value-rule ids (unknown id raises `ValueError`) |
| `is_placeholder(value, catalog=None)` | `None` or `{"rule_id", "kind", "notes"}` |
| `is_public_hint(name, catalog=None)` | `None` or `{"rule_id", "matched", "notes"}` |
| `luhn_ok(number)` | `bool`. Spaces and dashes ignored; any other non-digit, or fewer than 2 digits, is `False` |
| `card_brand(digits)` | `visa`, `mastercard`, `amex`, `discover`, `jcb`, `diners`, `unionpay` or `None` |
| `tokenize(identifier)` | list of `(token, starts_at_delimiter, ends_at_delimiter)` |
| `mask(value)` | first 4 and last 2 characters, stars between (values of 8 characters or fewer: first 2 then `***`) |

`context="cookie"` adds the cookie-name rules to the general rules: `N-CRED-COOKIE-HINT`
(name fragments such as `auth`, `sess`, `token`, `identity`) and `N-CRED-COOKIE-FRAMEWORK`
(fixed framework auth cookie names matched whole, such as `.AspNetCore.Identity.Application`,
so a trailing qualifier token cannot exclude them).

## Name result

```json
{
  "identifier": "userPasswordHash", "context": "any", "tokens": ["user", "password", "hash"],
  "sensitive": true, "category": "credential", "subcategory": "password", "canonical": "password",
  "tier": "core", "gdpr_special": false, "gdpr_article": null, "rule_id": "N-CRED-PASSWORD",
  "matched": "password", "position": "inner", "form": "hashed", "notes": "...",
  "excluded": null, "public_hint": null,
  "matches": [{"rule_id": "N-CRED-PASSWORD", "category": "credential", "subcategory": "password",
               "matched": "password", "position": "inner", "form": "hashed", "excluded_by": null}]
}
```

| Field | Meaning |
|---|---|
| `sensitive` | A rule matched and no qualifier or exclusion ruled it out. |
| `category` | One of `identifier`, `contact`, `financial`, `health`, `special-category`, `credential`, `secret`. `null` when not sensitive. |
| `subcategory` | Finer label, stable per rule: `date-of-birth`, `national-id`, `ip-address`, `device-id`, `geolocation`, `gender`, `age`, `signature`, `photo`, `email`, `phone`, `person-name`, `postal-address`, `postal-code`, `bank-account`, `payment-card`, `card-security`, `pay`, `health`, `special-category`, `criminal-record`, `password`, `security-answer`, `pin`, `otp`, `token`, `session`, `cookie`, `credential-derivative`, `application-secret`, `api-key`, `key-material`, `connection-string`, `service-credential`. |
| `canonical` | Canonical personal-data field (`email`, `phone`, `first_name`, `last_name`, `full_name`, `address`, `postal_code`, `date_of_birth`, `national_id`, `ip_address`, `device_id`, `geolocation`, `iban`, `card_number`, `card_security`, `salary`, `health`, `special_category`, `password`, `gender`, `age`, `signature`, `photo`). `password` also for credential derivatives (PasswordHash, Salt), so an inventory keeps hashed password columns under one field. `null` for secrets and session material. |
| `tier` | `core`, or `adjacent` for personal data of low sensitivity alone (gender, age, signature, photo). |
| `gdpr_special` | `true` for `health` and `special-category` (Art.9, and Art.10 criminal records). |
| `gdpr_article` | `Art.9`, `Art.10` or `null`. |
| `rule_id` | Name rule that won (`N-...`). The longest matched form wins, then the rightmost. |
| `matched` | The collapsed form that matched (`emailaddress`). |
| `position` | Where the form sits among the tokens: `whole`, `head`, `tail`, `inner`, or `substring` for run-on names matched by a substring form. |
| `form` | `plain`; `hashed` (hash, digest, bcrypt, sha*, md5, salted, or a derivative rule); `encrypted` (encrypt, cipher, crypted, trailing enc); `masked` (masked, mask, last4, redact, truncat, obfuscat). |
| `excluded` | When candidates existed but all were ruled out, or the name is an explicit exclusion: `{"rule_id", "reason", "would_be": {"rule_id", "category", "subcategory"} or null}`. Qualifier ids: `Q-METADATA-SUFFIX`, `Q-STRUCTURAL-SUFFIX`, `Q-REFERENCE-SUFFIX`, `Q-BOOLEAN-PREFIX`. Explicit ids: `X-...`. |
| `public_hint` | `is_public_hint(identifier)`, computed independently of `sensitive`. |
| `matches` | Every candidate considered, including excluded ones (`excluded_by` set). |

### Matching rules (fixed behaviour)

1. Tokens: split on non-alphanumerics and camelCase boundaries, lower-case.
2. A form matches the concatenation of 1-6 adjacent tokens, also after stripping trailing
   digits and a plural `s`, `es` or `ies`. `standalone_forms` must start and end at a
   delimiter (`user_age`, not `minPasswordAge`); `whole_forms` must be the entire identifier (`Hash`, not `cnic_hash`).
3. A candidate is excluded when:
   - it lies inside an explicit exclusion window (`name_exclusions`);
   - the token just before it is a boolean prefix (`is`, `has`, `show`, `use`, ...);
   - any token after it is a metadata or structural suffix;
   - the first token after it is a reference suffix (`id`, `uuid`, `ref`) the rule does not keep.
4. Substring forms apply only when no token candidate exists for that rule.

## Value match

```json
{
  "rule_id": "V-CARD", "kind": "format", "provider": null, "category": "financial",
  "subcategory": "payment-card", "canonical": "card_number", "form": "plain", "gdpr_special": false,
  "value": "4556 7375 8689 9855", "start": 120, "end": 139, "line": 7, "column": 44,
  "checksum": "luhn", "checksum_ok": true, "placeholder": null, "exposure": "personal",
  "sensitive": true, "locale": null, "confidence": "high", "cwe": "CWE-359", "priority": 15,
  "attributes": {"brand": "visa", "digits": 16}
}
```

| Field | Meaning |
|---|---|
| `rule_id` | Value rule id (`V-...`). Stable. |
| `kind` | `format` (a data format), `provider` (a vendor key format) or `assignment` (a literal assigned to a sensitive key name). |
| `provider` | Vendor for provider rules (`aws`, `stripe`, `sendgrid`, `github`, `slack`, `google`, `twilio`, `azure`, `npm`, `shopify`, `anthropic`, `openai`, `mailgun`, `mapbox`, `sentry`, `firebase`), else `null`. |
| `category`, `subcategory`, `canonical`, `form`, `gdpr_special` | As for names. For `assignment`, they come from classifying `attributes.key`. |
| `value`, `start`, `end` | Matched value and its offsets in `text`. For `assignment`, the literal without quotes. For other rules, the whole match (for example `Password=Qx7...`). |
| `line`, `column` | 1-based position of `start`. |
| `checksum`, `checksum_ok` | `luhn`, `iban-mod97`, `verhoeff` or `ssn-area`, with the result. Both `null` when the rule has no checksum. |
| `placeholder` | `is_placeholder` result for the secret part: the password inside a connection string or URL, the digits of a card, else the value. |
| `exposure` | `personal` (personal data), `secret`, `public` (public by design: Stripe `pk_`, Sentry DSN, GA id, Firebase app id, Mapbox `pk.`) or `conditional` (Google `AIza` keys: public only when restricted). |
| `sensitive` | `placeholder is None and checksum_ok is not False and exposure != "public" and not attributes.generic_mailbox`. |
| `locale` | ISO country for locale-specific national ids (`US`, `PK`, `GB`, `IN`, `SA`), else `null`. |
| `confidence` | `high`, `medium` or `low`. Unquoted assignments are always `low`. |
| `cwe` | Reference for the data type (`CWE-798`, `CWE-321`, `CWE-916`, `CWE-359`), or `null` for public identifiers. |
| `priority` | Rank used by `dedupe`. Higher wins when a value span lies inside another match. |
| `attributes` | Per rule, see below. |

`attributes` keys: V-CARD `brand` and `digits`; V-EMAIL `generic_mailbox` (role mailboxes
such as support@ and noreply@); V-URL-CREDENTIALS `user` and `host`; V-STRIPE-SECRET and
V-STRIPE-PUBLISHABLE `mode` (`live` or `test`); V-ASSIGNED-SECRET `key`, `key_rule_id`,
`quoted` and `public_hint` (the key's public-hint rule id or `null`).

Emission rules:
- **V-CARD** is returned when Luhn passes, when prefix and length fit a card scheme, or
  when the number is the old 16-digit 4/51-55/34/37 shape. The latter two can come back
  with `checksum_ok: false`.
- **V-AADHAAR-IN and V-NATIONAL-ID-SA** are returned only when their checksum passes.
- **V-EMAIL** rejects asset names (`logo@2x.png`).
- **V-ASSIGNED-SECRET** needs a 4+ character literal whose key classifies as
  `credential` or `secret`. It rejects member access, calls and `new`/`await` expressions.

`dedupe=True` drops a match whose value span lies inside a kept match with a higher
priority, or with equal priority and a longer span. Pass `dedupe=False` to get every
rule's matches, for example to map old per-rule output.

## Placeholder kinds

| kind | Meaning |
|---|---|
| `empty` | Empty, null, boolean or TBD literal. |
| `reference` | Env var, template, pipeline token or secret-store reference (`${X}`, `{{x}}`, `__X__`, `@Microsoft.KeyVault(`, "set in secret manager"). |
| `example-domain` | Email on example.com, test.local, localhost and similar. |
| `dummy` | Placeholder vocabulary (changeme, your_key, xxxx, ***, EXAMPLE, dummy, sample) or a fixture mailbox (test@, john.doe@). |
| `template` | Angle-bracket placeholder `<your-key>`. |
| `default-credential` | Well-known default or development credential (admin, root, sa, postgres, password, test). Still a literal: a consumer judging committed secrets may treat it as a weak real value. |
| `test-value` | Published test card, example SSN, fictional 555-01xx phone, provider documentation key. |
| `sequence` | Ascending or descending digit run. |
| `repeated` | Low character variety (`aaaa`, `0000000000000`). |

## CLI documents

All commands print one JSON document to stdout and exit 0 (2 when no command is given).

- `names`: `{"contract", "catalog_version", "count", "sensitive_count", "names": [name result without tokens/matches/notes]}`. `--verbose` includes the full result.
- `scan`: `{"contract", "catalog_version", "source", "values_masked", "count", "sensitive_count", "matches": [value match]}`. Values and `attributes.user` are masked unless `--show-values` is passed.
- `placeholder`: `{"results": [{"value", "placeholder"}]}`. `public`: `{"results": [{"name", "public_hint"}]}`. `luhn`: `{"results": [{"number", "luhn_ok", "brand"}]}`.
- `info`: catalog path, versions, category list, rule counts and rule ids.

## catalog.json schema

| Key | Content |
|---|---|
| `version` | Data version, semver. |
| `categories` | `{name: {"description", "gdpr_special"}}`. The seven names are fixed. |
| `tokenizer` | Description and `max_window`. |
| `name_rules[]` | `id`, `category`, `subcategory`, `canonical`, optional `tier`, `gdpr_article`, `form` (forced), `forms[]` (collapsed tokens), `standalone_forms[]`, `whole_forms[]`, `patterns[]` (regex, fullmatch on a token window), `substring_forms[]`, `keep_suffixes[]`, `contexts[]` (default `["any"]`), `notes`. |
| `name_qualifiers` | `metadata_suffixes`, `structural_suffixes`, `reference_suffixes`, `boolean_prefixes`, `hashed_markers`, `encrypted_markers`, `encrypted_last_tokens`, `masked_markers`, `masked_tokens`. |
| `name_exclusions[]` | `id`, `names[]` (collapsed), `reason`. |
| `value_rules[]` | `id`, `kind`, optional `provider`, `category`, `subcategory`, `canonical`, `form`, `exposure`, `priority`, `confidence`, `regex` (named groups `secret`, `user`, `host` honoured) or, for assignment, `regexes[]` with `quoted`, plus `name_categories` and `reject_value_regex`. Also optional `reject_regex`, `checksum`, `emit` (`checksum-only` or `checksum-or-brand`), `locale`, `generic_local_parts`, `cwe`, `notes`. |
| `placeholder_rules[]` | `id`, `kind`, `mode` (`fullmatch`, `search`, `digits`, `variety`), `regex` and/or `values`, `notes`. Evaluated in order; the first hit is returned. |
| `public_hints[]` | `id`, `substrings[]` (matched against the lower-cased name and its alphanumeric-only form), `notes`. |

## Stability promise

- **Within contract 1.x:**
  - No function or output field is removed, renamed or changes type.
  - The seven categories, the placeholder kinds, the `form` and `exposure` values do not change.
  - Rule ids are never reused for a different meaning.
  - New fields, subcategories, rules, forms, qualifiers and placeholder rules may be added. Consumers must ignore fields they do not know.
- **Catalog data changes bump `version`:**
  - patch: a form or notes tweak that cannot change a consumer's filter result;
  - minor: new rules, forms or exclusions;
  - major: a rule changes category, subcategory or exposure, or a rule is removed.
- **Consumer rule:** filter on `category`, `subcategory`, `form`, `exposure`, `placeholder`
  and `checksum_ok`. Test `rule_id` only to map to a legacy output name.
- **Recording changes:** any change that alters a consumer's output is recorded in this
  file's changelog in the same edit, and the affected consumer's owner is told.

## Deliberately not covered

Word lists that stay in consumer skills because they classify something other than
sensitive data. Do not move them here.

| Where | Why it stays |
|---|---|
| `audit-client-auth-and-storage/scripts/scan_secrets.py` `ENTROPY_NEAR_KEY`, `shannon()` | Entropy scoring is a heuristic, not a catalog fact. |
| `audit-infra-and-deployment/scripts/lint_infra.py` `SECRET_FILE_RE`, `EXAMPLE_RE`, CloudFormation property list (line 893) | File names and one IaC schema's property names, not data classification. |
| `audit-production-readiness-checklist/scripts/readiness_probe.py` `LOCALHOSTS`, `PROD_CONFIG`, `DEV_CONFIG` | Host and environment topology, owned by the readiness topic. |
| `audit-technical-debt/scripts/todo_age.py` `SECURITY_RE` | Security topic words for TODO triage (auth, csrf, payment), not sensitive data. |
| `audit-test-coverage-and-ci/scripts/test_inventory.py` auth area words | Test-area classification. |
| `audit-multi-tenant-isolation/scripts/data_access_paths.py` `TENANT_TOKENS`; `audit-gdpr-data-protection/scripts/gdpr_check.py` `SUBJECT`, `NON_SUBJECT` | Tenant keys and resource nouns, not sensitive data. |
| grep pattern files with secret regexes: `audit-client-auth-and-storage/scripts/patterns/{angular,react,vue}.json`, `audit-secrets-and-config/scripts/patterns/dotnet.json`, `audit-orm-query-and-data-access/scripts/patterns/dotnet.json` | Line patterns owned by consumers and run through `audit-code-scan`. They are not Python lists; a later pass can derive them from `value_rules`. |
| Documentation lists: `audit-logging-and-observability/references/sensitive-fields.md`, `audit-privacy-data-flow-mapper/references/pii-classification.md`, the public-identifier table in `audit-client-auth-and-storage/references/auth-flow-checklist.md` | Their word lists point at this skill; they keep their severity and remediation guidance. |

## Changelog

### 2026-09-11 - catalog 1.0 becomes the single source for consumer skills

Each consumer skill's own sensitive-name list was compared with the catalog over 8375
identifiers (every word of every list in six case styles plus every identifier in the
consumer fixtures) and 2333 text lines. A miss is an identifier a list matched and the
consumer's catalog filter does not; every miss is a deliberate qualifier exclusion (`Q-*`),
an explicit exclusion (`X-*`), or bare `signing`, which names a process rather than key
material. Re-run this comparison when a rule's category, subcategory or exposure changes.

| Consumer list (2026-09-11) | Its matches | Catalog misses | Of which NO RULE | Newly matched by catalog |
|---|---|---|---|---|
| `pii_scan.FIELD_PATTERNS` | 2587 | 698 | 0 | 1797 |
| `log_scan.SENSITIVE/NOT_SENSITIVE (classify_identifier)` | 616 | 9 | 0 | 2600 |
| `gdpr_check.PII_TOKEN` | 136 | 6 | 0 | 3556 |
| `config_key_inventory.SECRETY` | 917 | 363 | 23 | 449 |
| `scan_secrets.SECRET_NAMES` | 918 | 304 | 0 | 389 |
| `scan_secrets.PUBLIC_NAME_HINTS` | 266 | 0 | 0 | 50 |
| `extract_endpoints.SENSITIVE_FIELD` | 163 | 74 | 0 | 914 |
| `schema_checklist.SENSITIVE_RE minus HASHED_RE` | 86 | 0 | 0 | 1914 |
| `lint_infra.SECRET_NAME_RE` | 933 | 352 | 0 | 422 |
| `readiness_probe.SECRET_LINE (name part)` | 245 | 5 | 0 | 763 |
| `soc2_matrix.secrets_committed (name part)` | 224 | 5 | 0 | 784 |
| `check_headers.AUTH_COOKIE_HINT` | 895 | 198 | 0 | 3375 |
