#!/usr/bin/env python3
"""Grep environment files and built frontend bundles for secret-looking values.

Usage:
    python scan_secrets.py <repo_root> [--bundle <dir> ...] [--out secrets.json] [--md secrets.md]
                           [--no-bundle] [--min-entropy 3.5]

What is scanned:
  * Environment / config files anywhere under the repo (skipping node_modules etc.):
      environment*.ts|js, .env, .env.*, *.env, config*.js|ts|json, app.config.*,
      firebase*.ts|js|json, capacitor.config.*, next.config.*, nuxt.config.*, quasar.config.*
  * Built bundles: every *.js / *.mjs / *.html / *.json under the first existing
    of dist/, build/, www/, .next/static/, .output/public/, out/ (or the --bundle
    directories you pass). Minified files are scanned by regex windows, not lines.

What is reported (each hit has kind, file, line, key, masked value, why):
  * provider  - known secret prefixes (Stripe sk_, AWS AKIA, SendGrid SG., Slack xox, GitHub ghp_,
                Google AIza (public identifier unless unrestricted), Twilio SK/AC, private key blocks, JWTs)
  * keyname   - a key/variable whose name suggests a secret (secret, apiKey, privateKey, password,
                clientSecret, token, connectionString ...) assigned a literal of 8+ characters
  * entropy   - a quoted string of 20+ chars with Shannon entropy >= --min-entropy next to a
                key-like name (catches unlabelled random keys)
  * public_id - values that look like public identifiers (Firebase web config, Stripe pk_, Sentry DSN,
                GA measurement id) - listed so the reviewer can confirm restrictions; not secrets by default

Provider formats, secret key names, placeholders and public-by-design hints come from
audit-sensitive-data-catalog; the entropy heuristic stays in this script. Files are listed with
audit-code-scan's repo_walk.

Values are masked in the output (first 4 and last 2 characters). Everything is a
candidate: the skill decides public-identifier vs secret per references/auth-flow-checklist.md.
Read-only: nothing in the audited repo is modified.
"""
import argparse
import importlib.util
import json
import math
import os
import re
import sys

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

_SKILLS = _audit_core_skills_dir()
_WALK = os.path.join(_SKILLS, "audit-code-scan", "scripts", "repo_walk.py")
try:
    _spec = importlib.util.spec_from_file_location("audit_code_scan_repo_walk", _WALK)
    repo_walk = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(repo_walk)
except (FileNotFoundError, AttributeError, ImportError):
    sys.exit("audit-code-scan must be reachable from this skill (audit-core plugin or sibling layout; expected " + _WALK + ")")
_SDC_PATH = os.path.join(_SKILLS, "audit-sensitive-data-catalog", "scripts", "catalog.py")
if not os.path.exists(_SDC_PATH):
    sys.exit("audit-sensitive-data-catalog must be reachable from this skill (audit-core plugin or sibling layout; expected " + _SDC_PATH + ")")
_spec = importlib.util.spec_from_file_location("sensitive_data_catalog", _SDC_PATH)
sdc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sdc)

SECRETISH = ("credential", "secret")
BUNDLE_CANDIDATES = ["dist", "build", "www", os.path.join(".next", "static"), os.path.join(".output", "public"), "out"]
ENV_GLOBS = ["environment*.ts", "environment*.js", ".env", ".env.*", "*.env", "config*.js", "config*.ts",
             "config*.json", "app.config.*", "firebase*.ts", "firebase*.js", "firebase*.json",
             "capacitor.config.*", "next.config.*", "nuxt.config.*", "quasar.config.*", "appsettings*.json"]
BUNDLE_EXT = {".js", ".mjs", ".html", ".json", ".map"}

# catalog value rule id -> the provider name this script reported before the catalog existed
LEGACY_PROVIDER = {"V-STRIPE-SECRET": "stripe_secret", "V-STRIPE-PUBLISHABLE": "stripe_publishable",
                   "V-AWS-ACCESS-KEY-ID": "aws_access_key", "V-AWS-SECRET-KEY": "aws_secret_key",
                   "V-GOOGLE-API-KEY": "google_api_key", "V-GOOGLE-OAUTH-SECRET": "google_oauth_secret",
                   "V-SENDGRID": "sendgrid", "V-SLACK-TOKEN": "slack_token", "V-GITHUB-TOKEN": "github_token",
                   "V-TWILIO": "twilio_sid_or_key", "V-PEM-PRIVATE-KEY": "private_key_block", "V-JWT": "jwt",
                   "V-SENTRY-DSN": "sentry_dsn", "V-GA-MEASUREMENT-ID": "ga_measurement",
                   "V-FIREBASE-APP-ID": "firebase_app_id", "V-CONN-STRING-PASSWORD": "connection_string",
                   "V-URL-CREDENTIALS": "url_with_password"}
ENTROPY_NEAR_KEY = re.compile(
    r"(?i)\b(?P<key>[A-Za-z0-9_.-]*(?:key|token|secret|auth|cred|sign|salt|hash|id)[A-Za-z0-9_.-]*)\s*[:=]\s*['\"`](?P<val>[A-Za-z0-9+/=_\-.]{20,})['\"`]")


def shannon(s):
    if not s:
        return 0.0
    freq = {}
    for ch in s:
        freq[ch] = freq.get(ch, 0) + 1
    return -sum((c / len(s)) * math.log2(c / len(s)) for c in freq.values())


def mask(v):
    v = v.strip()
    if len(v) <= 8:
        return v[:2] + "***"
    return v[:4] + "*" * min(12, len(v) - 6) + v[-2:]


def iter_env_files(root):
    # Shared skip list from repo_walk (already skips dist, build, .next, .output) plus the other
    # build-output folders www/ and out/; bundles are scanned separately below.
    return repo_walk.iter_files(root, globs=ENV_GLOBS, extra_skip=("www", "out"), max_bytes=None)


def iter_bundle_files(bundle_dir):
    # A bundle folder is build output by definition, so build-output folder names below it are read.
    return repo_walk.iter_files(bundle_dir, exts=BUNDLE_EXT, include_dirs=("dist", "build", ".next", ".output"),
                                max_bytes=None)


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


def scan_text(text, rel, source, min_entropy, hits, seen):
    def add(kind, key, value, why, pos, cls):
        k = (rel, value[:16])   # one row per value; provider matches are recorded first and win
        if k in seen:
            return
        seen.add(k)
        hits.append({"kind": kind, "class": cls, "source": source, "file": rel, "line": line_of(text, pos),
                     "key": key, "value_masked": mask(value), "length": len(value), "why": why})

    for m in sdc.find_values(text):  # dedupe=True: a provider match wins over an assignment of the same value
        if m["category"] not in SECRETISH:
            continue
        if m["placeholder"] and m["placeholder"]["kind"] != "default-credential":
            continue
        if m["kind"] == "assignment":
            if not m["attributes"]["quoted"] or len(m["value"]) < 8:
                continue
            cls = "public_id" if m["attributes"]["public_hint"] else "secret"
            add("keyname", m["attributes"]["key"], m["value"], "key name suggests a credential", m["start"], cls)
        else:
            name = LEGACY_PROVIDER.get(m["rule_id"], m["rule_id"])
            cls = "public_id" if m["exposure"] in ("public", "conditional") else "secret"
            add("provider", name, m["value"], "matches %s format" % name, m["start"], cls)
    for m in ENTROPY_NEAR_KEY.finditer(text):
        key, val = m.group("key"), m.group("val")
        if sdc.is_placeholder(val):
            continue
        ent = shannon(val)
        if ent >= min_entropy:
            cls = "public_id" if sdc.is_public_hint(key) else "secret"
            add("entropy", key, val, f"entropy {ent:.2f} bits/char next to key-like name", m.start(), cls)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--bundle", action="append", default=[], help="built bundle directory (repeatable)")
    ap.add_argument("--no-bundle", action="store_true", help="skip bundle scanning")
    ap.add_argument("--out", default=None)
    ap.add_argument("--md", default=None)
    ap.add_argument("--min-entropy", type=float, default=3.5)
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    hits, seen = [], set()
    env_files = []
    for path in iter_env_files(root):
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        env_files.append(rel)
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                scan_text(fh.read(), rel, "env", args.min_entropy, hits, seen)
        except OSError:
            continue

    bundles = []
    if not args.no_bundle:
        cands = args.bundle or [os.path.join(root, c) for c in BUNDLE_CANDIDATES]
        for b in cands:
            b = b if os.path.isabs(b) else os.path.join(root, b)
            if os.path.isdir(b):
                bundles.append(os.path.relpath(b, root).replace(os.sep, "/"))
                for path in iter_bundle_files(b):
                    rel = os.path.relpath(path, root).replace(os.sep, "/")
                    try:
                        if os.path.getsize(path) > 25_000_000:
                            continue
                        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                            scan_text(fh.read(), rel, "bundle", args.min_entropy, hits, seen)
                    except OSError:
                        continue
                if args.bundle:
                    continue
                break  # default mode: first existing candidate only

    order = {"secret": 0, "public_id": 1}
    hits.sort(key=lambda h: (order.get(h["class"], 2), h["file"], h["line"]))
    result = {"root": root, "env_files_scanned": env_files, "bundles_scanned": bundles,
              "bundle_checked": bool(bundles), "hits": hits,
              "summary": {"secret_candidates": sum(1 for h in hits if h["class"] == "secret"),
                          "public_identifiers": sum(1 for h in hits if h["class"] == "public_id"),
                          "total": len(hits)}}
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
    if args.md:
        os.makedirs(os.path.dirname(os.path.abspath(args.md)) or ".", exist_ok=True)
        with open(args.md, "w", encoding="utf-8") as fh:
            fh.write(f"Bundle checked: {'yes (' + ', '.join(bundles) + ')' if bundles else 'no - no build output found'}\n\n")
            fh.write("| File | Line | Key name | Looks like | Public identifier or secret? | Finding |\n|---|---|---|---|---|---|\n")
            for h in hits:
                fh.write(f"| `{h['file']}` | {h['line']} | {h['key']} | {h['kind']}: {h['why']} ({h['value_masked']}) | "
                         f"{'secret (verify)' if h['class'] == 'secret' else 'public identifier (verify restrictions)'} |  |\n")
    print(json.dumps(result["summary"] | {"bundle_checked": bool(bundles)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
