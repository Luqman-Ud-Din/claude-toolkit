---
name: audit-sensitive-data-catalog
description: Single source of truth for what counts as sensitive data in an audit - classifies names (fields, columns, config keys, cookies) split from camelCase, snake_case and kebab-case into tokens, and finds sensitive values in text (email, phone, IBAN, Luhn-checked cards, national ids, JWTs, private keys, connection-string passwords, AWS, Stripe, SendGrid, GitHub, Slack, Google and Azure keys) with a category, GDPR special-category flag, placeholder detection and public-by-design hints. Use it when the user asks whether a field or value is PII, personal data, a secret or sensitive, why passwordPolicy or tokenExpiry is not flagged, whether a key is a placeholder or public, whether a card passes Luhn, or wants to add a sensitive name or secret format - even if the skill is not named. Also used by audit-privacy-data-flow-mapper, audit-logging-and-observability, audit-gdpr-data-protection, audit-secrets-and-config, audit-client-auth-and-storage, audit-api-contract, audit-db-schema and other audit skills.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-core:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit sensitive-data catalog

One job: answer "is this name or this value sensitive data, and what kind" with one
rule set that every audit skill shares. Before this skill existed, eight scripts each
kept their own password, token and PII word lists, and they disagreed. One flagged
`passwordPolicy`, another missed `customerEmail`, and a third treated `ipAddress` as
not personal. The catalog records the facts once, so every report uses the same words.

The skill does not scan repositories and does not decide findings. Consumers walk
files, pick the names and strings that matter to their topic, and call the matcher.
Whether a sensitive name in a log call, an API response or a column is a finding is
the consumer's call.

Read-only rule: nothing in an audited repository is modified. The module reads only
`references/catalog.json`. The CLI also reads the one file you name.

## Inputs and prerequisites

- Strings the caller already has: identifier names, lines, snippets, config values.
- Python 3, standard library only.
- No stack detection is needed. The rules are language-agnostic, since `userPassword`
  is the same risk in C#, TypeScript and YAML, so `audit/stack.json` is not read.
- No file walking. Consumers walk with `audit-code-scan`'s `repo_walk.py`. The CLI's
  `scan <file>` reads that single file through `repo_walk.read_text`, so it decodes
  files and applies the size cap exactly like every other audit script.

## Workflow

1. **Pick the call that matches what you hold.**

   | You have | Call | CLI |
   |---|---|---|
   | one identifier | `classify_name(name, context="any")` | `names <name> ...` |
   | a cookie name | `classify_name(name, context="cookie")` | `names --context cookie <name>` |
   | a line of code with identifiers in it | `find_names(line)` | - |
   | a line, file body or blob | `find_values(text)` | `scan <file or ->` |
   | a single config value | `is_placeholder(value)` | `placeholder <value>` |
   | a key name that may be public by design | `is_public_hint(name)` | `public <name>` |
   | a card-like number | `luhn_ok(number)` | `luhn <number>` |

2. **Import it from a consumer script** by path under a unique module name. Several
   skills ship a `catalog.py`, so a bare `import catalog` can load the wrong file:

   ```python
   import importlib.util, os, sys
   _SKILLS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
   _CAT = os.path.join(_SKILLS, "audit-sensitive-data-catalog", "scripts", "catalog.py")
   if not os.path.exists(_CAT):
       sys.exit("audit-sensitive-data-catalog must be installed next to this skill (expected " + _CAT + ")")
   _spec = importlib.util.spec_from_file_location("sensitive_data_catalog", _CAT)
   sdc = importlib.util.module_from_spec(_spec)
   _spec.loader.exec_module(sdc)
   ```

3. **Filter on contract fields, never on your own word list.** Use `sensitive`,
   `category`, `subcategory`, `form`, `exposure`, `placeholder` and `checksum_ok`.
   Examples: a logging audit keeps `form == "plain"` so `passwordHash` is not reported
   as a leaked password. An API over-exposure check keeps credential derivatives
   because a hash in a response is still a leak. Each consumer documents its own
   filter in its SKILL.md.

4. **Answer ad-hoc questions from the CLI.** For "is `X` sensitive":

   ```bash
   python <skills-dir>/audit-sensitive-data-catalog/scripts/catalog.py names userPasswordHash passwordPolicy X-Api-Key
   python <skills-dir>/audit-sensitive-data-catalog/scripts/catalog.py scan config/app.env --sensitive-only
   ```

   Quote the `rule_id` and, for a name that is not sensitive, `excluded.reason`. The
   reason explains the decision (for example "'policy' after the name makes it metadata
   about the value"). `scan` masks values by default. Keep them masked in anything you
   write, and use `--show-values` only when the user asks to see them.

5. **Say what the result does not prove.** A sensitive name does not prove the
   variable holds a real value, and a placeholder verdict does not prove the key was
   never real (check history with `audit-git-history`). A public exposure only means
   the value is designed to be public. A Google browser key (`exposure: conditional`)
   is public only if its restrictions are confirmed.

6. **Change the catalog, not a consumer.** To add a field name or a secret format:
   - Add a collapsed form (`firstname`, not `first_name`) to the right `name_rules`
     entry, or add a `value_rules` entry with an id, category, exposure, priority and
     notes.
   - Run `python scripts/catalog.py info`. Loading fails when one form appears in two rules.
   - Re-run both fixtures (`names --file evals/files/names.txt` and
     `scan evals/files/mixed-sample.txt --show-values`) and confirm nothing else moved.
   - Bump `version` in `catalog.json`. If a consumer's output changes, record the
     difference in the contract's changelog and tell the consumer's owner.

   Never add a synonym list inside a consumer script. That recreates the drift this
   skill removed.

## Output contract

The field-by-field contract, the catalog.json schema and the stability promise are
in `references/sensitive-data-catalog-contract.md`. In short:

- `classify_name` returns `sensitive`, `category`, `subcategory`, `canonical`, `tier`,
  `gdpr_special`, `gdpr_article`, `rule_id`, `matched`, `position`, `form`
  (plain, hashed, encrypted or masked), `excluded` (`rule_id`, `reason`, `would_be`)
  when a match was ruled out, `public_hint` and every candidate in `matches`.
- `find_values` returns matches with `rule_id`, `kind`, `category`, `subcategory`,
  `value`, `start`, `end`, `line`, `column`, `checksum_ok`, `placeholder`, `exposure`
  (personal, secret, public or conditional), `sensitive`, `locale`, `confidence`, `cwe`
  and `attributes` (brand, key, host, generic_mailbox, mode).
- `is_placeholder` and `is_public_hint` return `None` or a small dict with `rule_id`.
- CLI output is JSON with `contract` and `catalog_version` on every document.

## Limits

- **Names are words, not data.** A sensitive name can hold a masked or empty value,
  and an innocent name such as `data` or `notes` can hold anything. Consumers still
  open the file.
- **Run-on lower-case names** (`userfirstname`) only match through substring forms,
  which exist for strong words only: password, secret, api key, private key,
  connection string, credential and session id.
- **Qualifiers are English.** `passwordPolicy` is excluded; `politicaContrasena` is not matched at all.
- **National ids cover US, PK, GB, IN and SA only.** Other countries' ids are missed.
  Saudi ids and phone numbers are low confidence because many numbers share their shape.
- **No entropy scoring.** Random-looking strings next to key-like names stay a
  consumer heuristic (for example `scan_secrets.py`).
- **Regex values are not parsed.** A PEM header split across string concatenations,
  or a key built at runtime, is not found.
- **The module returns raw values.** Mask them before writing evidence (`catalog.mask`).

## Bundled files

- `scripts/catalog.py` - loader, name classifier, value finder, placeholder and public-hint tests, Luhn, CLI.
- `references/catalog.json` - the data: categories, name rules, qualifiers, exclusions, value rules, placeholders, public hints.
- `references/sensitive-data-catalog-contract.md` - API, output fields, catalog schema, stability promise.
- `evals/` - a names list and a mixed text sample with planted values (valid and Luhn-failing cards, a placeholder key, a publishable Stripe key).
