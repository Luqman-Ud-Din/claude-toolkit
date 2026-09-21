#!/usr/bin/env python3
"""Sensitive-data catalog: classify identifier names and find sensitive values in text.

The single source of truth for what counts as sensitive data is
references/catalog.json. This module loads it and applies it; it never walks a
repository and never decides whether something is a finding.

Usage (CLI):
    python catalog.py names <identifier> [<identifier> ...] [--context any|cookie]
    python catalog.py names --file names.txt [--context cookie]
    python catalog.py scan <file | -> [--sensitive-only] [--show-values] [--rules V-EMAIL,V-CARD] [--no-dedupe]
    python catalog.py placeholder <value> [<value> ...]
    python catalog.py public <name> [<name> ...]
    python catalog.py luhn <number> [<number> ...]
    python catalog.py info
  Common option: --catalog <path> to load a different catalog.json.
  Output is JSON on stdout. `scan` masks values unless --show-values is given.
  In a names file, blank lines and '#' lines are skipped and anything after '=>' is ignored.

Usage (module):
    import catalog
    cat = catalog.load()                      # optional; functions load the default lazily
    catalog.classify_name("userPasswordHash") # -> dict, see references/sensitive-data-catalog-contract.md
    catalog.find_names("logger.info(user.email)")
    catalog.find_values(text)                 # -> list of value matches
    catalog.is_placeholder("changeme")        # -> dict or None
    catalog.is_public_hint("NEXT_PUBLIC_KEY") # -> dict or None
    catalog.luhn_ok("4556 7375 8689 9855")    # -> bool

Python 3 standard library only. Read-only: the only file this reads is the
catalog and, for `scan <file>`, the one file named.
"""
import argparse
import bisect
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

def _audit_core_skills_dir():
    """Resolve the explicit core installation, or the original sibling layout."""
    env = os.environ.get("AUDIT_CORE_ROOT")
    if env:
        skills = os.path.join(env, "skills")
        if os.path.isdir(os.path.join(skills, "audit-code-scan")):
            return skills
        sys.exit("AUDIT_CORE_ROOT does not contain audit-core skills: " + env)
    sibling = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if os.path.isdir(os.path.join(sibling, "audit-code-scan")):
        return sibling
    sys.exit("audit-core is unavailable. Enable audit-core and restart Claude Code, "
             "or set AUDIT_CORE_ROOT to its plugin directory when running manually.")

DEFAULT_PATH = os.path.normpath(os.path.join(HERE, "..", "references", "catalog.json"))
CONTRACT_VERSION = "1.0"

_CAMEL1 = re.compile(r"([a-z0-9])([A-Z])")
_CAMEL2 = re.compile(r"([A-Z]+)([A-Z][a-z])")
_SPLIT = re.compile(r"[^A-Za-z0-9]+")
_TRAILING_DIGITS = re.compile(r"\d+$")
_IDENT_IN_TEXT = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*(?:[.:\-][A-Za-z_$][A-Za-z0-9_$]*)*")


# --------------------------------------------------------------------------- checksums
def luhn_ok(number):
    """True when the digits of `number` pass the Luhn (mod 10) check.

    Spaces and dashes are ignored. Any other non-digit character, or fewer than
    two digits, returns False."""
    s = str(number).strip()
    if not s or re.search(r"[^\d \-]", s):
        return False
    digits = re.sub(r"\D", "", s)
    if len(digits) < 2:
        return False
    total, alt = 0, False
    for ch in reversed(digits):
        n = int(ch)
        if alt:
            n *= 2
            if n > 9:
                n -= 9
        total += n
        alt = not alt
    return total % 10 == 0


def _iban_ok(value):
    v = re.sub(r"\s", "", value).upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", v):
        return False
    moved = v[4:] + v[:4]
    num = "".join(str(int(c, 36)) for c in moved)
    return int(num) % 97 == 1


_VD = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 2, 3, 4, 0, 6, 7, 8, 9, 5], [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
       [3, 4, 0, 1, 2, 8, 9, 5, 6, 7], [4, 0, 1, 2, 3, 9, 5, 6, 7, 8], [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
       [6, 5, 9, 8, 7, 1, 0, 4, 3, 2], [7, 6, 5, 9, 8, 2, 1, 0, 4, 3], [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
       [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]]
_VP = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 5, 7, 6, 2, 8, 3, 0, 9, 4], [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
       [8, 9, 1, 6, 0, 4, 3, 5, 2, 7], [9, 4, 5, 3, 1, 2, 6, 8, 7, 0], [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
       [2, 7, 9, 3, 8, 0, 6, 4, 1, 5], [7, 0, 4, 6, 9, 1, 3, 2, 5, 8]]


def _verhoeff_ok(value):
    digits = re.sub(r"\D", "", value)
    c = 0
    for i, ch in enumerate(reversed(digits)):
        c = _VD[c][_VP[i % 8][int(ch)]]
    return bool(digits) and c == 0


def _ssn_ok(value):
    m = re.fullmatch(r"(\d{3})-(\d{2})-(\d{4})", value)
    if not m:
        return False
    area, group, serial = m.groups()
    return area not in ("000", "666") and not area.startswith("9") and group != "00" and serial != "0000"


_CHECKSUMS = {"luhn": luhn_ok, "iban-mod97": _iban_ok, "verhoeff": _verhoeff_ok, "ssn-area": _ssn_ok}


def card_brand(digits):
    """Card scheme implied by prefix and length, or None."""
    d = re.sub(r"\D", "", str(digits))
    n = len(d)
    if n < 13:
        return None
    p2, p3, p4, p6 = int(d[:2]), int(d[:3]), int(d[:4]), int(d[:6])
    if d[0] == "4" and n in (13, 16, 19):
        return "visa"
    if (51 <= p2 <= 55 or 2221 <= p4 <= 2720) and n == 16:
        return "mastercard"
    if p2 in (34, 37) and n == 15:
        return "amex"
    if (p4 == 6011 or p2 == 65 or 644 <= p3 <= 649 or 622126 <= p6 <= 622925) and 16 <= n <= 19:
        return "discover"
    if 3528 <= p4 <= 3589 and 16 <= n <= 19:
        return "jcb"
    if (300 <= p3 <= 305 or p2 in (36, 38)) and 14 <= n <= 19:
        return "diners"
    if p2 == 62 and 16 <= n <= 19:
        return "unionpay"
    return None


# --------------------------------------------------------------------------- tokenizer
def tokenize(identifier):
    """Split an identifier into lower-case tokens.

    Returns a list of (token, starts_at_delimiter, ends_at_delimiter). Splits on
    every non-alphanumeric character and on camelCase / PascalCase boundaries."""
    out = []
    for seg in _SPLIT.split(str(identifier)):
        if not seg:
            continue
        parts = _CAMEL2.sub(r"\1 \2", _CAMEL1.sub(r"\1 \2", seg)).split()
        for k, p in enumerate(parts):
            out.append((p.lower(), k == 0, k == len(parts) - 1))
    return out


def _variants(w):
    vs = [w]
    stripped = _TRAILING_DIGITS.sub("", w)
    if stripped and stripped != w:
        vs.append(stripped)
    for x in list(vs):
        if len(x) > 4 and x.endswith("ies"):
            vs.append(x[:-3] + "y")
        if len(x) > 4 and x.endswith("es"):
            vs.append(x[:-2])
        if len(x) > 3 and x.endswith("s") and not x.endswith("ss"):
            vs.append(x[:-1])
    return vs


# --------------------------------------------------------------------------- catalog object
class Catalog(object):
    """Compiled view of catalog.json. Build with load()."""

    def __init__(self, data, path=None):
        self.data = data
        self.path = path
        self.version = data.get("version")
        self.max_window = int(data.get("tokenizer", {}).get("max_window", 6))
        self.categories = data["categories"]
        self.rules = {r["id"]: r for r in data["name_rules"]}
        self.form_index = {}
        self.pattern_rules = []
        self.substring_rules = []
        for r in data["name_rules"]:
            if r["category"] not in self.categories:
                raise ValueError("name rule %s has unknown category %s" % (r["id"], r["category"]))
            for key, standalone in (("forms", False), ("standalone_forms", "delimited"), ("whole_forms", "whole")):
                for f in r.get(key, []):
                    for other, _ in self.form_index.get(f, []):
                        if set(_contexts(other)) & set(_contexts(r)):
                            raise ValueError("form %r is in both %s and %s" % (f, other["id"], r["id"]))
                    self.form_index.setdefault(f, []).append((r, standalone))
            for p in r.get("patterns", []):
                self.pattern_rules.append((r, re.compile(p)))
            if r.get("substring_forms"):
                self.substring_rules.append((r, list(r["substring_forms"])))
        q = data["name_qualifiers"]
        self.metadata = set(q["metadata_suffixes"])
        self.structural = set(q["structural_suffixes"])
        self.reference = set(q["reference_suffixes"])
        self.boolean_prefixes = set(q["boolean_prefixes"])
        self.hashed_markers = list(q["hashed_markers"])
        self.encrypted_markers = list(q["encrypted_markers"])
        self.encrypted_last = set(q["encrypted_last_tokens"])
        self.masked_markers = list(q["masked_markers"])
        self.masked_tokens = set(q["masked_tokens"])
        self.exclusions = {}
        for e in data["name_exclusions"]:
            for nm in e["names"]:
                self.exclusions[nm] = e
        self.value_rules = []
        for r in data["value_rules"]:
            c = dict(r)
            if r["kind"] == "assignment":
                c["_regexes"] = [(x["quoted"], re.compile(x["regex"])) for x in r["regexes"]]
                c["_reject_value"] = re.compile(r["reject_value_regex"]) if r.get("reject_value_regex") else None
            else:
                c["_regex"] = re.compile(r["regex"])
                c["_reject"] = re.compile(r["reject_regex"]) if r.get("reject_regex") else None
            self.value_rules.append(c)
        self.value_rule_ids = {r["id"] for r in self.value_rules}
        self.placeholders = []
        for p in data["placeholder_rules"]:
            c = dict(p)
            patterns = [p["regex"]] if p.get("regex") else []
            for variable in p.get("env_values", []):
                value = os.environ.get(variable)
                if value:
                    patterns.append(re.escape(value))
            if patterns:
                c["_regex"] = re.compile("|".join(patterns))
            if p.get("values"):
                c["_values"] = set(p["values"])
            self.placeholders.append(c)
        self.public_hints = data["public_hints"]


def _contexts(rule):
    return rule.get("contexts") or ["any"]


_DEFAULT = None


def load(path=None):
    """Load and compile a catalog. path=None loads references/catalog.json next to this script."""
    global _DEFAULT
    p = os.path.abspath(path) if path else DEFAULT_PATH
    with open(p, "r", encoding="utf-8") as fh:
        cat = Catalog(json.load(fh), p)
    if path is None:
        _DEFAULT = cat
    return cat


def _cat(catalog):
    if catalog is not None:
        return catalog
    return _DEFAULT if _DEFAULT is not None else load()


# --------------------------------------------------------------------------- names
def _rule_summary(cat, rule):
    cinfo = cat.categories[rule["category"]]
    return {
        "category": rule["category"],
        "subcategory": rule["subcategory"],
        "canonical": rule.get("canonical"),
        "tier": rule.get("tier", "core"),
        "gdpr_special": bool(cinfo.get("gdpr_special")),
        "gdpr_article": rule.get("gdpr_article"),
        "rule_id": rule["id"],
        "notes": rule.get("notes", ""),
    }


def _form_of(cat, rule, others_joined, others, last_token, match_is_last):
    if rule.get("form"):
        return rule["form"]
    if any(m in others_joined for m in cat.hashed_markers):
        return "hashed"
    if any(m in others_joined for m in cat.encrypted_markers) or (last_token in cat.encrypted_last and not match_is_last):
        return "encrypted"
    if any(m in others_joined for m in cat.masked_markers) or (set(others) & cat.masked_tokens):
        return "masked"
    return "plain"


def _token_exclusion(cat, rule, words, i, j, excl_ranges):
    for a, b, e in excl_ranges:
        if a <= i and j <= b:
            return e["id"], e["reason"]
    if i > 0 and (words[i - 1] in cat.boolean_prefixes or words[0] in cat.boolean_prefixes):
        verb = words[i - 1] if words[i - 1] in cat.boolean_prefixes else words[0]
        return "Q-BOOLEAN-PREFIX", "'%s' prefix makes it a flag or action about the value, not the value" % verb
    suffix = [(_TRAILING_DIGITS.sub("", w) or w) for w in words[j:]]
    for s in suffix:
        if s in cat.metadata:
            return "Q-METADATA-SUFFIX", "'%s' after the name makes it metadata about the value, not the value" % s
        if s in cat.structural:
            return "Q-STRUCTURAL-SUFFIX", "'%s' after the name makes it a code or UI construct, not the value" % s
    if suffix and suffix[0] in cat.reference and suffix[0] not in rule.get("keep_suffixes", []):
        return "Q-REFERENCE-SUFFIX", "'%s' after the name makes it a reference to a record, not the value" % suffix[0]
    return None


def _substring_exclusion(cat, collapsed, form, idx):
    for nm, e in cat.exclusions.items():
        if form in nm and nm in collapsed:
            return e["id"], e["reason"]
    before = collapsed[:idx]
    if before in cat.boolean_prefixes:
        return "Q-BOOLEAN-PREFIX", "'%s' prefix makes it a flag or action about the value, not the value" % before
    rest = collapsed[idx + len(form):]
    for r in (rest, rest[1:] if rest.startswith("s") else rest, rest[2:] if rest.startswith("es") else rest):
        for q in sorted(cat.metadata | cat.structural, key=len, reverse=True):
            if len(q) >= 3 and r.startswith(q):
                kind = "Q-METADATA-SUFFIX" if q in cat.metadata else "Q-STRUCTURAL-SUFFIX"
                return kind, "'%s' after the name makes it metadata or a code construct, not the value" % q
    return None


def classify_name(identifier, context="any", catalog=None):
    """Classify one identifier (field, property, column, config key, header or cookie name).

    context='cookie' also enables the cookie-name rules. Returns the dict described
    in references/sensitive-data-catalog-contract.md."""
    cat = _cat(catalog)
    toks = tokenize(identifier)
    words = [t[0] for t in toks]
    n = len(words)
    collapsed = "".join(words)
    result = {
        "identifier": identifier, "context": context, "tokens": words, "sensitive": False,
        "category": None, "subcategory": None, "canonical": None, "tier": None,
        "gdpr_special": False, "gdpr_article": None, "rule_id": None, "matched": None,
        "position": None, "form": None, "notes": "", "excluded": None,
        "public_hint": is_public_hint(identifier, catalog=cat), "matches": [],
    }
    if n == 0:
        return result

    excl_ranges, cands = [], []
    for i in range(n):
        acc = ""
        for j in range(i + 1, min(n, i + cat.max_window) + 1):
            acc += words[j - 1]
            for v in _variants(acc):
                e = cat.exclusions.get(v)
                if e:
                    excl_ranges.append((i, j, e))
                for rule, standalone in cat.form_index.get(v, []):
                    if "any" not in _contexts(rule) and context not in _contexts(rule):
                        continue
                    if standalone == "delimited" and not (toks[i][1] and toks[j - 1][2]):
                        continue
                    if standalone == "whole" and not (i == 0 and j == n):
                        continue
                    cands.append((rule, i, j, v))
                for rule, rx in cat.pattern_rules:
                    if ("any" in _contexts(rule) or context in _contexts(rule)) and rx.fullmatch(v):
                        cands.append((rule, i, j, v))
    seen, evaluated = set(), []
    for rule, i, j, v in cands:
        key = (rule["id"], i, j)
        if key in seen:
            continue
        seen.add(key)
        excl = _token_exclusion(cat, rule, words, i, j, excl_ranges)
        pos = "whole" if (i == 0 and j == n) else "tail" if j == n else "head" if i == 0 else "inner"
        others = words[:i] + words[j:]
        form = _form_of(cat, rule, "".join(others), others, words[-1], j == n)
        evaluated.append({"rule": rule, "i": i, "j": j, "matched": v, "position": pos, "form": form, "excl": excl})
    token_rule_ids = {e["rule"]["id"] for e in evaluated}
    for rule, forms in cat.substring_rules:
        if rule["id"] in token_rule_ids or ("any" not in _contexts(rule) and context not in _contexts(rule)):
            continue
        for f in forms:
            idx = collapsed.find(f)
            if idx < 0:
                continue
            excl = _substring_exclusion(cat, collapsed, f, idx)
            rest = collapsed[:idx] + collapsed[idx + len(f):]
            form = _form_of(cat, rule, rest, [], "", True)
            evaluated.append({"rule": rule, "i": -1, "j": -1, "matched": f, "position": "substring", "form": form, "excl": excl})
            break

    for e in evaluated:
        result["matches"].append({
            "rule_id": e["rule"]["id"], "category": e["rule"]["category"], "subcategory": e["rule"]["subcategory"],
            "matched": e["matched"], "position": e["position"], "form": e["form"],
            "excluded_by": e["excl"][0] if e["excl"] else None,
        })
    live = [e for e in evaluated if not e["excl"]]
    if live:
        best = max(live, key=lambda e: (len(e["matched"]), e["i"]))
        result.update(_rule_summary(cat, best["rule"]))
        result.update({"sensitive": True, "matched": best["matched"], "position": best["position"], "form": best["form"]})
    elif evaluated:
        best = max(evaluated, key=lambda e: (len(e["matched"]), e["i"]))
        result["excluded"] = {"rule_id": best["excl"][0], "reason": best["excl"][1],
                              "would_be": {"rule_id": best["rule"]["id"], "category": best["rule"]["category"],
                                           "subcategory": best["rule"]["subcategory"]}}
    elif excl_ranges:
        e = max(excl_ranges, key=lambda x: x[1] - x[0])[2]
        result["excluded"] = {"rule_id": e["id"], "reason": e["reason"], "would_be": None}
    return result


def find_names(text, context="any", catalog=None, sensitive_only=True):
    """Classify every identifier-like run in a line or snippet (dotted, colon and kebab joins kept).

    Returns classify_name results extended with start and end offsets. With
    sensitive_only=False, unmatched identifiers are returned too."""
    cat = _cat(catalog)
    out = []
    for m in _IDENT_IN_TEXT.finditer(str(text)):
        r = classify_name(m.group(0), context=context, catalog=cat)
        if r["sensitive"] or not sensitive_only:
            r["start"], r["end"] = m.start(), m.end()
            out.append(r)
    return out


def is_public_hint(name, catalog=None):
    """Return {"rule_id", "matched", "notes"} when the name marks a public-by-design value, else None."""
    cat = _cat(catalog)
    low = str(name).lower()
    collapsed = re.sub(r"[^a-z0-9]", "", low)
    for h in cat.public_hints:
        for s in h["substrings"]:
            if s in low or s in collapsed:
                return {"rule_id": h["id"], "matched": s, "notes": h.get("notes", "")}
    return None


# --------------------------------------------------------------------------- placeholders
def is_placeholder(value, catalog=None):
    """Return {"rule_id", "kind", "notes"} when the value is a placeholder, dummy, reference,
    default credential or published test value, else None."""
    cat = _cat(catalog)
    v = "" if value is None else str(value)
    s = v.strip().strip("\"'`")
    digitish = bool(re.fullmatch(r"[\d \-]+", s)) and any(ch.isdigit() for ch in s)
    digits = re.sub(r"\D", "", s) if digitish else ""
    for p in cat.placeholders:
        mode = p.get("mode", "search")
        hit = False
        if mode == "fullmatch":
            hit = bool(p["_regex"].fullmatch(s))
        elif mode == "search":
            hit = bool(p["_regex"].search(s))
        elif mode == "digits":
            if digits:
                hit = (digits in p.get("_values", ())) or bool(p.get("_regex") and p["_regex"].fullmatch(digits))
        elif mode == "variety":
            compact = digits if digitish else s
            hit = (len(compact) >= 4 and len(set(compact)) <= 2) or (digitish and len(digits) >= 13 and len(set(digits)) <= 3)
        if hit:
            return {"rule_id": p["id"], "kind": p["kind"], "notes": p.get("notes", "")}
    return None


# --------------------------------------------------------------------------- values
class _Lines(object):
    def __init__(self, text):
        self.starts = [0] + [m.end() for m in re.finditer(r"\n", text)]

    def locate(self, pos):
        i = bisect.bisect_right(self.starts, pos) - 1
        return i + 1, pos - self.starts[i] + 1


def _value_match(cat, rule, text, lines, start, end, secret_part, attributes, category=None, subcategory=None,
                 canonical=None, form=None, confidence=None):
    value = text[start:end]
    checksum_ok = None
    if rule.get("checksum"):
        checksum_ok = _CHECKSUMS[rule["checksum"]](value)
    ph = is_placeholder(secret_part, catalog=cat)
    exposure = rule.get("exposure", "secret")
    cat_name = category if category is not None else rule.get("category")
    cinfo = cat.categories.get(cat_name, {}) if cat_name else {}
    sensitive = (ph is None and checksum_ok is not False and exposure != "public"
                 and not attributes.get("generic_mailbox"))
    line, col = lines.locate(start)
    return {
        "rule_id": rule["id"], "kind": rule["kind"], "provider": rule.get("provider"),
        "category": cat_name, "subcategory": subcategory if subcategory is not None else rule.get("subcategory"),
        "canonical": canonical if canonical is not None else rule.get("canonical"),
        "form": form or rule.get("form", "plain"), "gdpr_special": bool(cinfo.get("gdpr_special")),
        "value": value, "start": start, "end": end, "line": line, "column": col,
        "checksum": rule.get("checksum"), "checksum_ok": checksum_ok, "placeholder": ph,
        "exposure": exposure, "sensitive": bool(sensitive), "locale": rule.get("locale"),
        "confidence": confidence or rule.get("confidence", "medium"), "cwe": rule.get("cwe"),
        "priority": rule.get("priority", 0), "attributes": attributes,
    }


def _span(m):
    if "value" in m.re.groupindex and m.group("value") is not None:
        return m.start("value"), m.end("value")
    return m.start(), m.end()


def find_values(text, catalog=None, rules=None, dedupe=True):
    """Find sensitive-value candidates in a string.

    rules: optional iterable of value-rule ids to run (default all). With dedupe=True a
    match whose value span lies inside a higher-priority match is dropped. Returns the
    list described in references/sensitive-data-catalog-contract.md, sorted by position."""
    cat = _cat(catalog)
    text = "" if text is None else str(text)
    wanted = set(rules) if rules else None
    if wanted:
        unknown = wanted - cat.value_rule_ids
        if unknown:
            raise ValueError("unknown value rule id(s): " + ", ".join(sorted(unknown)))
    lines = _Lines(text)
    out = []
    for rule in cat.value_rules:
        if wanted and rule["id"] not in wanted:
            continue
        if rule["kind"] == "assignment":
            for quoted, rx in rule["_regexes"]:
                for m in rx.finditer(text):
                    key, val = m.group("key"), m.group("value")
                    if not quoted and rule["_reject_value"] and rule["_reject_value"].search(val.strip()):
                        continue
                    nr = classify_name(key, catalog=cat)
                    if not nr["sensitive"] or nr["category"] not in rule["name_categories"]:
                        continue
                    ph_hint = is_public_hint(key, catalog=cat)
                    attrs = {"key": key, "key_rule_id": nr["rule_id"], "quoted": quoted,
                             "public_hint": ph_hint["rule_id"] if ph_hint else None}
                    out.append(_value_match(cat, rule, text, lines, m.start("value"), m.end("value"), val, attrs,
                                            category=nr["category"], subcategory=nr["subcategory"],
                                            canonical=nr["canonical"], form=nr["form"],
                                            confidence=rule.get("confidence") if quoted else "low"))
            continue
        for m in rule["_regex"].finditer(text):
            start, end = _span(m)
            value = text[start:end]
            if rule.get("_reject") and rule["_reject"].search(value):
                continue
            attrs = {}
            secret_part = m.group("secret") if "secret" in m.re.groupindex and m.group("secret") else value
            if "host" in m.re.groupindex:
                attrs["host"] = m.group("host")
                attrs["user"] = m.group("user")
            if rule["id"] == "V-EMAIL":
                local = value.split("@", 1)[0].lower()
                attrs["generic_mailbox"] = local in rule.get("generic_local_parts", [])
            if rule["id"] == "V-CARD":
                digits = re.sub(r"\D", "", value)
                if not 13 <= len(digits) <= 19:
                    continue
                brand = card_brand(digits)
                legacy_shape = len(digits) == 16 and bool(re.match(r"4|5[1-5]|3[47]", digits))
                if not (luhn_ok(digits) or brand or legacy_shape):
                    continue
                attrs["brand"] = brand
                attrs["digits"] = len(digits)
                secret_part = digits
            if rule["id"] in ("V-STRIPE-SECRET", "V-STRIPE-PUBLISHABLE"):
                attrs["mode"] = "live" if "_live_" in value else "test"
            vm = _value_match(cat, rule, text, lines, start, end, secret_part, attrs)
            if rule.get("emit") == "checksum-only" and vm["checksum_ok"] is not True:
                continue
            out.append(vm)
    if dedupe:
        ranked = sorted(out, key=lambda x: (-x["priority"], -(x["end"] - x["start"]), x["start"]))
        kept = []
        for m in ranked:
            if any(k["start"] <= m["start"] and m["end"] <= k["end"] for k in kept):
                continue
            kept.append(m)
        out = kept
    out.sort(key=lambda x: (x["start"], -x["priority"]))
    return out


# --------------------------------------------------------------------------- CLI
def mask(value):
    v = str(value).strip()
    if len(v) <= 8:
        return v[:2] + "***"
    return v[:4] + "*" * min(12, len(v) - 6) + v[-2:]


def _read_file(path):
    """Read one file through audit-code-scan's shared reader (same decoding and size cap as every audit)."""
    skills = _audit_core_skills_dir()
    walk = os.path.join(skills, "audit-code-scan", "scripts", "repo_walk.py")
    try:
        spec = importlib.util.spec_from_file_location("audit_code_scan_repo_walk", walk)
        repo_walk = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(repo_walk)
    except (FileNotFoundError, AttributeError, ImportError):
        sys.exit("audit-code-scan must be reachable from this skill (expected " + walk + ")")
    if os.path.getsize(path) > repo_walk.MAX_BYTES:
        sys.exit("%s is larger than %d bytes; audit-code-scan skips such files" % (path, repo_walk.MAX_BYTES))
    return repo_walk.read_text(path)


def _names_from_file(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            s = line.split("=>", 1)[0].strip()
            if s and not s.startswith("#"):
                yield s


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--catalog", help="catalog.json to load (default: references/catalog.json)")
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("names", help="classify identifier names")
    p.add_argument("identifiers", nargs="*")
    p.add_argument("--file", help="file with one identifier per line")
    p.add_argument("--context", default="any", choices=["any", "cookie"])
    p.add_argument("--verbose", action="store_true", help="include tokens and every candidate match")
    p = sub.add_parser("scan", help="find sensitive values in one file or stdin")
    p.add_argument("source", help="file path, or - for stdin")
    p.add_argument("--sensitive-only", action="store_true")
    p.add_argument("--show-values", action="store_true", help="print raw values (default: masked)")
    p.add_argument("--rules", help="comma-separated value rule ids")
    p.add_argument("--no-dedupe", action="store_true")
    p = sub.add_parser("placeholder", help="test values against the placeholder rules")
    p.add_argument("values", nargs="+")
    p = sub.add_parser("public", help="test names against the public-by-design hints")
    p.add_argument("names", nargs="+")
    p = sub.add_parser("luhn", help="Luhn-check numbers")
    p.add_argument("numbers", nargs="+")
    sub.add_parser("info", help="catalog version and rule counts")
    a = ap.parse_args(argv)
    if not a.cmd:
        ap.print_help()
        return 2
    cat = load(a.catalog) if a.catalog else load()

    if a.cmd == "names":
        idents = list(a.identifiers)
        if a.file:
            idents += list(_names_from_file(a.file))
        if not idents:
            sys.exit("names: pass identifiers or --file")
        res = []
        for ident in idents:
            r = classify_name(ident, context=a.context, catalog=cat)
            if not a.verbose:
                r = {k: r[k] for k in ("identifier", "sensitive", "category", "subcategory", "canonical", "tier",
                                       "gdpr_special", "rule_id", "matched", "position", "form", "excluded", "public_hint")}
            res.append(r)
        doc = {"contract": CONTRACT_VERSION, "catalog_version": cat.version, "count": len(res),
               "sensitive_count": sum(1 for r in res if r["sensitive"]), "names": res}
    elif a.cmd == "scan":
        if a.source == "-":
            text, source = sys.stdin.read(), "stdin"
        else:
            if not os.path.isfile(a.source):
                sys.exit("scan: no such file: " + a.source)
            text, source = _read_file(a.source), os.path.abspath(a.source)
        rules = [x.strip() for x in a.rules.split(",")] if a.rules else None
        try:
            matches = find_values(text, catalog=cat, rules=rules, dedupe=not a.no_dedupe)
        except ValueError as e:
            sys.exit(str(e))
        if a.sensitive_only:
            matches = [m for m in matches if m["sensitive"]]
        if not a.show_values:
            for m in matches:
                m["value"] = mask(m["value"])
                if "user" in m["attributes"] and m["attributes"]["user"]:
                    m["attributes"]["user"] = mask(m["attributes"]["user"])
        doc = {"contract": CONTRACT_VERSION, "catalog_version": cat.version, "source": source,
               "values_masked": not a.show_values, "count": len(matches),
               "sensitive_count": sum(1 for m in matches if m["sensitive"]), "matches": matches}
    elif a.cmd == "placeholder":
        doc = {"results": [{"value": v, "placeholder": is_placeholder(v, catalog=cat)} for v in a.values]}
    elif a.cmd == "public":
        doc = {"results": [{"name": n, "public_hint": is_public_hint(n, catalog=cat)} for n in a.names]}
    elif a.cmd == "luhn":
        doc = {"results": [{"number": n, "luhn_ok": luhn_ok(n), "brand": card_brand(n)} for n in a.numbers]}
    else:
        d = cat.data
        doc = {"catalog": cat.path, "catalog_version": cat.version, "contract": CONTRACT_VERSION,
               "categories": sorted(d["categories"]), "name_rules": len(d["name_rules"]),
               "name_forms": len(cat.form_index), "name_exclusions": sum(len(e["names"]) for e in d["name_exclusions"]),
               "value_rules": [r["id"] for r in d["value_rules"]],
               "placeholder_rules": [p["id"] for p in d["placeholder_rules"]],
               "public_hints": [h["id"] for h in d["public_hints"]]}
    json.dump(doc, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
