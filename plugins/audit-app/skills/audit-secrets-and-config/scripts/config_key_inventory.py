#!/usr/bin/env python3
"""Inventory every configuration key and where its value comes from.

Produces the "config key -> source" table the audit requires: for each key, is
it read from a config FILE (and does that file hold a literal value), from an
ENV var, or from a SECRET MANAGER (Key Vault, AWS Secrets Manager, Google Secret
Manager, Vault, user-secrets, Docker/K8s secrets)? Keys whose value is a literal
in a committed file - especially secret-looking ones - are flagged.

Usage:
    python config_key_inventory.py <repo_root> [--out keys.json] [--md keys.md]

Sources detected:
  file          - key defined in appsettings*.json / *.env / *.yml / *.properties / config.*
  env           - read via env var (Environment.GetEnvironmentVariable, process.env, os.environ, ${VAR})
  secret-mgr    - Key Vault / Secrets Manager / Vault / user-secrets / *_FILE secret mounts
Read-only: never modifies the audited repo.
"""
import argparse
import importlib.util
import json
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

SECRET_MGR = re.compile(r"(?i)(SecretClient|KeyVault|GetSecret|SecretsManager|secretsmanager|hashicorp|vault|AddUserSecrets|user-secrets|SecretManager|/run/secrets/|_FILE\b|valueFrom:\s*\n?\s*secretKeyRef|google.*SecretManager|AccessSecretVersion)")
ENV_READ = re.compile(r"(GetEnvironmentVariable|process\.env\.|os\.environ|os\.getenv|System\.getenv|ENV\[|\$\{?[A-Z][A-Z0-9_]{2,}\}?)")


def iter_files(root, exts=None):
    # Shared skip list from repo_walk. Config files have arbitrary names (.env.example,
    # appsettings.Production.json), so without exts every file name is accepted.
    if exts is None:
        return repo_walk.iter_files(root, globs=["*"])
    return repo_walk.iter_files(root, exts=set(exts))


def _flatten_json(obj, prefix=""):
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}:{k}" if prefix else k
            out.update(_flatten_json(v, key))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.update(_flatten_json(v, f"{prefix}[{i}]"))
    else:
        out[prefix] = obj
    return out


def scan_config_files(root):
    rows = []
    cfg_names = {".json", ".env", ".yml", ".yaml", ".properties", ".ini", ".toml", ".config"}
    for path in iter_files(root):
        base = os.path.basename(path).lower()
        ext = os.path.splitext(base)[1]
        is_cfg = ext in cfg_names or base.startswith(("appsettings", "web.config", ".env")) or base.endswith(".env")
        if not is_cfg:
            continue
        rel = repo_walk.rel(root, path)
        is_example = "example" in base or "sample" in base or "template" in base or base.endswith(".dist")
        try:
            raw = open(path, "r", encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        pairs = {}
        if ext == ".json" or base.startswith("appsettings"):
            try:
                pairs = _flatten_json(json.loads(raw))
            except json.JSONDecodeError:
                pairs = {}
        if not pairs:
            for i, line in enumerate(raw.splitlines(), 1):
                m = re.match(r"\s*([A-Za-z0-9_.:\-]+)\s*[:=]\s*(.+?)\s*$", line)
                if m and not line.lstrip().startswith(("#", "//", ";")):
                    pairs[m.group(1)] = m.group(2)
        for key, val in pairs.items():
            sval = "" if val is None else str(val)
            nr = sdc.classify_name(key)
            secret = nr["sensitive"] and nr["category"] in SECRETISH
            ph = sdc.is_placeholder(sval)
            # a well-known default credential (admin, sa, postgres) is still a committed literal
            literal = sval != "" and (ph is None or ph["kind"] == "default-credential")
            rows.append({
                "key": key, "source": "file", "file": rel,
                "has_literal_value": literal,
                "looks_secret": secret,
                "is_example_file": is_example,
                "flag": secret and literal and not is_example,
                "secret_rule": nr["rule_id"],
                "placeholder": ph["kind"] if ph else None,
                "value_preview": (sval[:12] + "...") if len(sval) > 12 else sval,
            })
    return rows


def scan_code_sources(root):
    rows = []
    code_ext = {".cs", ".java", ".kt", ".js", ".ts", ".py", ".yml", ".yaml"}
    for path in iter_files(root, code_ext):
        rel = repo_walk.rel(root, path)
        try:
            lines = open(path, "r", encoding="utf-8", errors="ignore").readlines()
        except OSError:
            continue
        for n, line in enumerate(lines, 1):
            if SECRET_MGR.search(line):
                rows.append({"key": line.strip()[:80], "source": "secret-mgr", "file": rel,
                             "line": n, "has_literal_value": False, "looks_secret": True,
                             "flag": False})
            elif ENV_READ.search(line):
                rows.append({"key": line.strip()[:80], "source": "env", "file": rel,
                             "line": n, "has_literal_value": False,
                             "looks_secret": any(r["category"] in SECRETISH for r in sdc.find_names(line)), "flag": False})
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--out")
    ap.add_argument("--md")
    args = ap.parse_args()

    rows = scan_config_files(args.root) + scan_code_sources(args.root)
    flagged = [r for r in rows if r.get("flag")]
    doc = {"root": os.path.abspath(args.root), "count": len(rows),
           "flagged_count": len(flagged),
           "note": "keys with a literal secret value in a committed file are flagged; confirm before reporting",
           "keys": rows}
    text = json.dumps(doc, indent=2)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(args.out)
    else:
        print(text)
    if args.md:
        with open(args.md, "w", encoding="utf-8") as fh:
            fh.write("| Key | Source | Literal value? | Secret-like? | Flag | Location |\n")
            fh.write("|---|---|---|---|---|---|\n")
            for r in rows:
                loc = r["file"] + (f":{r['line']}" if r.get("line") else "")
                fh.write(f"| `{r['key']}` | {r['source']} | {r.get('has_literal_value')} | "
                         f"{r.get('looks_secret')} | {'YES' if r.get('flag') else ''} | `{loc}` |\n")
        print(args.md)
    print(f"# {len(rows)} config keys, {len(flagged)} flagged (literal secret in committed file)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
