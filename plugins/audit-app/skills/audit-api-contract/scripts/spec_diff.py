#!/usr/bin/env python3
"""Diff two OpenAPI documents (2.0 or 3.x) and list breaking and notable changes.

Usage:
    python spec_diff.py <old_spec> <new_spec> [--out spec-diff.json] [--md spec-diff.md] [--fail-on-breaking]

Formats: JSON always; YAML if PyYAML is installed (pip install pyyaml). Detects:
  breaking
    * removed paths and removed operations (method on a path)
    * removed path/query/header parameters, parameters that became required
    * request body fields removed or newly required, type/format changed, enum values removed
    * response fields removed, type/format changed, enum values removed (per status code, JSON media types)
    * response status codes removed
    * security added to an operation that had none
  notable (non-breaking, still worth recording)
    * added paths/operations, added optional fields, added enum values, added status codes
    * deprecated flags added

$ref pointers are resolved against components/schemas (3.x) or definitions (2.0); allOf is merged
shallowly; oneOf/anyOf are compared by their first branch only (recorded as "approximate").
Exit code 0 normally; 2 with --fail-on-breaking when breaking changes exist. Read-only.
"""
import argparse
import json
import os
import sys

METHODS = ("get", "post", "put", "patch", "delete", "head", "options", "trace")
JSON_MEDIA = ("application/json", "application/problem+json", "*/*")


def load(path):
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    if path.lower().endswith((".yaml", ".yml")):
        try:
            import yaml  # type: ignore
        except ImportError:
            sys.exit(f"{path} is YAML but PyYAML is not installed; run 'pip install pyyaml' or convert to JSON")
        return yaml.safe_load(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        try:
            import yaml  # type: ignore
        except ImportError:
            sys.exit(f"{path} is not valid JSON ({exc}) and PyYAML is not installed to try YAML")
        return yaml.safe_load(text)


class Spec:
    def __init__(self, doc):
        self.doc = doc or {}
        self.v2 = "swagger" in self.doc
        self.schemas = (self.doc.get("definitions") if self.v2 else (self.doc.get("components") or {}).get("schemas")) or {}
        self.approx = []

    def lookup(self, ref):
        """Follow a local JSON pointer (#/components/parameters/X, #/definitions/Y, ...)."""
        if not isinstance(ref, str) or not ref.startswith("#/"):
            return {}
        node = self.doc
        for part in ref[2:].split("/"):
            part = part.replace("~1", "/").replace("~0", "~")
            if not isinstance(node, dict) or part not in node:
                return self.schemas.get(ref.split("/")[-1], {})
            node = node[part]
        return node

    def resolve(self, schema, depth=0):
        if not isinstance(schema, dict) or depth > 12:
            return schema or {}
        if "$ref" in schema:
            return self.resolve(self.lookup(schema["$ref"]), depth + 1)
        if "allOf" in schema:
            merged = {"type": "object", "properties": {}, "required": []}
            for part in schema["allOf"]:
                r = self.resolve(part, depth + 1)
                merged["properties"].update(r.get("properties", {}))
                merged["required"] += r.get("required", [])
            return merged
        for k in ("oneOf", "anyOf"):
            if k in schema and schema[k]:
                self.approx.append(k)
                return self.resolve(schema[k][0], depth + 1)
        return schema

    def operations(self):
        out = {}
        for path, item in (self.doc.get("paths") or {}).items():
            if not isinstance(item, dict):
                continue
            for m in METHODS:
                if m in item:
                    out[(path, m.upper())] = item[m] or {}
        return out

    def params(self, op, path_item=None):
        res = {}
        for p in (path_item or {}).get("parameters", []) + op.get("parameters", []):
            p = self.resolve(p)
            if p.get("in") == "body":  # swagger 2
                continue
            res[(p.get("in"), p.get("name"))] = p
        return res

    def request_schema(self, op):
        if self.v2:
            for p in op.get("parameters", []):
                if p.get("in") == "body":
                    return self.resolve(p.get("schema"))
            return None
        content = ((op.get("requestBody") or {}).get("content") or {})
        for media in JSON_MEDIA:
            if media in content:
                return self.resolve(content[media].get("schema"))
        return self.resolve(next(iter(content.values()), {}).get("schema")) if content else None

    def response_schema(self, resp):
        resp = self.resolve(resp)
        if self.v2:
            return self.resolve(resp.get("schema")) if resp.get("schema") else None
        content = resp.get("content") or {}
        for media in JSON_MEDIA:
            if media in content:
                return self.resolve(content[media].get("schema"))
        return self.resolve(next(iter(content.values()), {}).get("schema")) if content else None


def flatten(spec, schema, prefix="", depth=0, seen=None):
    """Return {field_path: {type, format, enum, required}} for an object schema (arrays descend into items)."""
    seen = seen or set()
    schema = spec.resolve(schema)
    out = {}
    if not isinstance(schema, dict) or depth > 8:
        return out
    if schema.get("type") == "array" or "items" in schema:
        return flatten(spec, schema.get("items", {}), prefix + "[]", depth + 1, seen)
    required = set(schema.get("required", []))
    for name, sub in (schema.get("properties") or {}).items():
        sub = spec.resolve(sub)
        key = f"{prefix}.{name}" if prefix else name
        out[key] = {"type": sub.get("type", "object" if sub.get("properties") else ""), "format": sub.get("format", ""),
                    "enum": list(sub.get("enum", [])), "required": name in required}
        if sub.get("properties") or sub.get("items"):
            out.update(flatten(spec, sub, key, depth + 1, seen))
    return out


def diff_fields(old, new, where, changes, direction):
    """direction: 'request' (removed/newly-required/type change are breaking) or 'response' (removed/type change breaking)."""
    for k, o in old.items():
        if k not in new:
            changes.append({"kind": "breaking", "change": f"{direction} field removed", "where": where, "detail": k})
            continue
        n = new[k]
        if o["type"] != n["type"] or (o["format"] and n["format"] and o["format"] != n["format"]):
            changes.append({"kind": "breaking", "change": f"{direction} field type changed", "where": where,
                            "detail": f"{k}: {o['type'] or '?'}{('/' + o['format']) if o['format'] else ''} -> {n['type'] or '?'}{('/' + n['format']) if n['format'] else ''}"})
        if o["enum"]:
            removed = [v for v in o["enum"] if v not in n["enum"]]
            added = [v for v in n["enum"] if v not in o["enum"]]
            if removed:
                changes.append({"kind": "breaking", "change": f"{direction} enum values removed", "where": where, "detail": f"{k}: {removed}"})
            if added:
                changes.append({"kind": "notable", "change": f"{direction} enum values added", "where": where, "detail": f"{k}: {added}"})
        if direction == "request" and not o["required"] and n["required"]:
            changes.append({"kind": "breaking", "change": "request field became required", "where": where, "detail": k})
    for k, n in new.items():
        if k not in old:
            if direction == "request" and n["required"]:
                changes.append({"kind": "breaking", "change": "new required request field", "where": where, "detail": k})
            else:
                changes.append({"kind": "notable", "change": f"{direction} field added", "where": where, "detail": k})


def diff(old_doc, new_doc):
    old, new = Spec(old_doc), Spec(new_doc)
    changes = []
    oops, nops = old.operations(), new.operations()
    old_paths = {p for p, _ in oops}
    new_paths = {p for p, _ in nops}
    for p in sorted(old_paths - new_paths):
        changes.append({"kind": "breaking", "change": "path removed", "where": p, "detail": ""})
    for p in sorted(new_paths - old_paths):
        changes.append({"kind": "notable", "change": "path added", "where": p, "detail": ""})
    for key in sorted(oops):
        if key not in nops:
            if key[0] in new_paths:
                changes.append({"kind": "breaking", "change": "operation removed", "where": f"{key[1]} {key[0]}", "detail": ""})
            continue
        o, n = oops[key], nops[key]
        where = f"{key[1]} {key[0]}"
        # parameters
        op_ = old.params(o, (old.doc.get("paths") or {}).get(key[0]))
        np_ = new.params(n, (new.doc.get("paths") or {}).get(key[0]))
        for pk, pv in op_.items():
            if pk not in np_:
                changes.append({"kind": "breaking", "change": "parameter removed", "where": where, "detail": f"{pk[0]}:{pk[1]}"})
            else:
                ot = (pv.get("schema") or pv).get("type", "")
                nt = (np_[pk].get("schema") or np_[pk]).get("type", "")
                if ot and nt and ot != nt:
                    changes.append({"kind": "breaking", "change": "parameter type changed", "where": where, "detail": f"{pk[0]}:{pk[1]} {ot} -> {nt}"})
                if not pv.get("required") and np_[pk].get("required"):
                    changes.append({"kind": "breaking", "change": "parameter became required", "where": where, "detail": f"{pk[0]}:{pk[1]}"})
        for pk, pv in np_.items():
            if pk not in op_:
                changes.append({"kind": "breaking" if pv.get("required") else "notable",
                                "change": "new required parameter" if pv.get("required") else "parameter added", "where": where, "detail": f"{pk[0]}:{pk[1]}"})
        # request body
        orq, nrq = old.request_schema(o), new.request_schema(n)
        if orq or nrq:
            diff_fields(flatten(old, orq or {}), flatten(new, nrq or {}), where + " (request)", changes, "request")
        # responses
        ores, nres = o.get("responses") or {}, n.get("responses") or {}
        for code in ores:
            if code not in nres:
                changes.append({"kind": "breaking", "change": "response status removed", "where": where, "detail": str(code)})
                continue
            os_, ns_ = old.response_schema(ores[code]), new.response_schema(nres[code])
            if not os_ and ns_:
                changes.append({"kind": "notable", "change": "response schema documented", "where": f"{where} (response {code})", "detail": ""})
            elif os_ and not ns_:
                changes.append({"kind": "breaking", "change": "response schema removed", "where": f"{where} (response {code})", "detail": ""})
            elif os_ and ns_:
                diff_fields(flatten(old, os_ or {}), flatten(new, ns_ or {}), f"{where} (response {code})", changes, "response")
        for code in nres:
            if code not in ores:
                changes.append({"kind": "notable", "change": "response status added", "where": where, "detail": str(code)})
        # security / deprecation
        o_sec = o.get("security", old.doc.get("security"))
        n_sec = n.get("security", new.doc.get("security"))
        if not o_sec and n_sec:
            changes.append({"kind": "breaking", "change": "security requirement added", "where": where, "detail": json.dumps(n_sec)})
        elif o_sec and not n_sec:
            changes.append({"kind": "notable", "change": "security requirement removed (check this is intended)", "where": where, "detail": json.dumps(o_sec)})
        if not o.get("deprecated") and n.get("deprecated"):
            changes.append({"kind": "notable", "change": "operation deprecated", "where": where, "detail": ""})
    for key in sorted(set(nops) - set(oops)):
        if key[0] in old_paths:
            changes.append({"kind": "notable", "change": "operation added", "where": f"{key[1]} {key[0]}", "detail": ""})
    approx = sorted(set(old.approx + new.approx))
    return changes, approx


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument("--out")
    ap.add_argument("--md")
    ap.add_argument("--fail-on-breaking", action="store_true")
    args = ap.parse_args()

    changes, approx = diff(load(args.old), load(args.new))
    breaking = [c for c in changes if c["kind"] == "breaking"]
    result = {"old": os.path.abspath(args.old), "new": os.path.abspath(args.new),
              "breaking_count": len(breaking), "notable_count": len(changes) - len(breaking),
              "approximations": approx, "changes": changes}
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
    if args.md:
        os.makedirs(os.path.dirname(os.path.abspath(args.md)) or ".", exist_ok=True)
        with open(args.md, "w", encoding="utf-8") as fh:
            fh.write(f"Old: `{args.old}`  New: `{args.new}`  Breaking: {len(breaking)}  Notable: {len(changes) - len(breaking)}\n\n")
            fh.write("| Kind | Change | Where | Detail |\n|---|---|---|---|\n")
            for c in changes:
                fh.write(f"| {c['kind']} | {c['change']} | `{c['where']}` | {c['detail'].replace('|', '/')} |\n")
            if approx:
                fh.write(f"\nApproximate comparisons (first branch only): {', '.join(approx)}\n")
    print(json.dumps({"breaking": len(breaking), "notable": len(changes) - len(breaking),
                      "breaking_changes": [f"{c['change']}: {c['where']} {c['detail']}".strip() for c in breaking]}, indent=2))
    return 2 if (args.fail_on_breaking and breaking) else 0


if __name__ == "__main__":
    sys.exit(main())
