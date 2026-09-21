#!/usr/bin/env python3
"""Discover infrastructure components (databases, brokers, caches, gateways,
app services), their replica counts and dependents, and flag single-instance
components on which many flows depend (single points of failure).

Usage:
    python topology_scan.py <repo_root> [--out topology.json] [--md topology.md]

Sources (stdlib only - a small indentation-based YAML reader is used, so exotic
YAML may be partially read; the output says which files were parsed):
  docker-compose*.yml / compose*.yml   services: image, deploy.replicas, depends_on, ports
  Kubernetes manifests (*.yml/*.yaml with kind: Deployment|StatefulSet)   metadata.name, spec.replicas
  Helm values*.yaml                    replicaCount
  Config: appsettings*.json, application*.yml|properties, .env*, config/*.ts|js|py
        host names / URLs for postgres, mysql, sqlserver, mongodb, redis, rabbitmq/amqp, kafka,
        nats, servicebus, sqs -> which app units depend on which infra component

Roles by image/name/URL: database, broker, cache, gateway, search, storage, app.
SPOF candidates: infra components with replicas <= 1 and >= 1 dependent, or with the
most dependents overall. Read-only against the audited repo.
"""
import argparse
import json
import os
import re
import sys

import importlib.util

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


def _load_atomic(skill, module, alias):
    """Load an atomic skill's script by path under a unique module name."""
    path = os.path.join(_SKILLS, skill, "scripts", module + ".py")
    if not os.path.exists(path):
        sys.exit(f"{skill} must be reachable from this skill (audit-core plugin or sibling layout; expected {path})")
    spec = importlib.util.spec_from_file_location(alias, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


repo_walk = _load_atomic("audit-code-scan", "repo_walk", "audit_code_scan_repo_walk")

ROLE_RX = [
    ("database", r"(postgres|postgis|mysql|mariadb|mssql|sqlserver|sql-server|mongo|cockroach|oracle|db2|timescale|clickhouse|cassandra|dynamodb|cosmos)"),
    ("broker", r"(rabbitmq|amqp|kafka|redpanda|nats|activemq|artemis|servicebus|service-bus|sqs|sns|pubsub|mosquitto|mqtt|zeromq|eventhub|kinesis)"),
    ("cache", r"(redis|memcached|valkey|keydb|dragonfly|hazelcast)"),
    ("search", r"(elasticsearch|opensearch|solr|meilisearch|typesense)"),
    ("storage", r"(minio|s3|azurite|blob|gcs)"),
    ("gateway", r"(nginx|traefik|haproxy|envoy|kong|ocelot|yarp|gateway|apigw|caddy|ingress)"),
    ("observability", r"(prometheus|grafana|jaeger|zipkin|otel|loki|seq|elk|kibana|tempo)"),
]
CONFIG_KEYS = re.compile(r"(?i)(postgres|pgsql|mysql|mariadb|sqlserver|mssql|Server=|Data Source=|mongodb|redis|rabbitmq|amqp|kafka|nats|servicebus|sqs|elasticsearch)")


def _read(p):
    return repo_walk.read_text(p)


def role_of(*texts):
    blob = " ".join(t or "" for t in texts).lower()
    for role, rx in ROLE_RX:
        if re.search(rx, blob):
            return role
    return "app"


# --- minimal YAML reader: nested dicts/lists of scalars, enough for compose/k8s
def yaml_lite(text):
    lines = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        lines.append(raw.rstrip())
    docs, cur = [], []
    for l in lines:
        if l.strip() == "---":
            if cur:
                docs.append(cur)
            cur = []
        else:
            cur.append(l)
    if cur:
        docs.append(cur)
    return [_parse_block(d, 0)[0] for d in docs]


def _indent(l):
    return len(l) - len(l.lstrip(" "))


def _scalar(v):
    v = v.strip()
    if v.startswith(("'", '"')) and v.endswith(("'", '"')) and len(v) >= 2:
        return v[1:-1]
    if v.startswith("[") and v.endswith("]"):
        return [_scalar(x) for x in v[1:-1].split(",") if x.strip()]
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    return v


def _parse_block(lines, i):
    """Parse lines[i:] at the indentation of lines[i]; return (obj, next_i)."""
    if i >= len(lines):
        return None, i
    base = _indent(lines[i])
    if lines[i].lstrip().startswith("- "):
        out = []
        while i < len(lines) and _indent(lines[i]) == base and lines[i].lstrip().startswith("- "):
            item = lines[i].lstrip()[2:]
            if ":" in item and not item.strip().startswith(("'", '"', "http")):
                # inline mapping start: "- name: x" then deeper keys
                sub = [" " * (base + 2) + item] + []
                j = i + 1
                while j < len(lines) and _indent(lines[j]) > base:
                    sub.append(lines[j]); j += 1
                obj, _ = _parse_block(sub, 0)
                out.append(obj); i = j
            else:
                out.append(_scalar(item)); i += 1
        return out, i
    out = {}
    while i < len(lines) and _indent(lines[i]) == base and not lines[i].lstrip().startswith("- "):
        l = lines[i].strip()
        m = re.match(r"([^:]+?)\s*:\s*(.*)$", l)
        if not m:
            i += 1
            continue
        k, v = m.group(1).strip().strip("'\""), m.group(2)
        if v.strip() and not v.strip().startswith("#"):
            out[k] = _scalar(v.split(" #")[0])
            i += 1
        else:
            j = i + 1
            if j < len(lines) and _indent(lines[j]) > base:
                out[k], i = _parse_block(lines, j)
            else:
                out[k] = None; i = j
    return out, i


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root"); ap.add_argument("--out"); ap.add_argument("--md")
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    comps, parsed, deps = {}, [], []

    def comp(name, source, **kw):
        c = comps.setdefault(name.lower(), {"name": name, "role": "app", "replicas": None, "sources": [], "dependents": set(), "ports": [], "image": None, "notes": []})
        if source not in c["sources"]:
            c["sources"].append(source)
        for k, v in kw.items():
            if v is not None and (c.get(k) in (None, [], "app") or k == "replicas"):
                c[k] = v
        return c

    # globs=("*",): compose, k8s, .env* and config files are matched by name below, not by extension.
    for p in repo_walk.iter_files(root, globs=("*",)):
        dirpath, fn = os.path.split(p)
        rp = repo_walk.rel(root, p); low = fn.lower()
        if re.match(r"(docker-)?compose[\w.-]*\.ya?ml$", low):
            parsed.append(rp)
            for doc in yaml_lite(_read(p)):
                if not isinstance(doc, dict):
                    continue
                for sname, svc in (doc.get("services") or {}).items():
                    if not isinstance(svc, dict):
                        continue
                    image = svc.get("image") or ("build:" + str(svc.get("build"))) if (svc.get("image") or svc.get("build")) else None
                    replicas = None
                    dep = svc.get("deploy") or {}
                    if isinstance(dep, dict) and isinstance(dep.get("replicas"), int):
                        replicas = dep["replicas"]
                    if replicas is None:
                        replicas = 1
                    c = comp(sname, rp, image=image, replicas=replicas, role=role_of(sname, image))
                    ports = svc.get("ports") or []
                    c["ports"] = [str(x) for x in ports] if isinstance(ports, list) else [str(ports)]
                    for d in (svc.get("depends_on") or []):
                        dname = d if isinstance(d, str) else str(d)
                        deps.append((sname, dname, f"{rp} depends_on"))
                    if isinstance(svc.get("depends_on"), dict):
                        for dname in svc["depends_on"]:
                            deps.append((sname, dname, f"{rp} depends_on"))
                    env = svc.get("environment") or {}
                    env_items = env.items() if isinstance(env, dict) else [(str(e).split("=", 1)[0], str(e).split("=", 1)[-1]) for e in env]
                    for k, v in env_items:
                        for other in list(comps):
                            if other != sname.lower() and re.search(r"\b" + re.escape(other) + r"\b", str(v).lower()):
                                deps.append((sname, other, f"{rp} env {k}"))
        elif low.endswith((".yml", ".yaml")) and "kind:" in _read(p)[:20000]:
            text = _read(p)
            if re.search(r"^kind:\s*(Deployment|StatefulSet|DaemonSet)", text, re.M):
                parsed.append(rp)
                for doc in yaml_lite(text):
                    if not isinstance(doc, dict) or doc.get("kind") not in ("Deployment", "StatefulSet", "DaemonSet"):
                        continue
                    name = (doc.get("metadata") or {}).get("name", fn)
                    spec = doc.get("spec") or {}
                    reps = spec.get("replicas") if isinstance(spec.get("replicas"), int) else 1
                    image = None
                    try:
                        image = spec["template"]["spec"]["containers"][0].get("image")
                    except Exception:
                        pass
                    comp(str(name), rp, image=image, replicas=reps, role=role_of(str(name), image))
        elif re.match(r"values[\w.-]*\.ya?ml$", low):
            text = _read(p)
            m = re.search(r"^replicaCount:\s*(\d+)", text, re.M)
            if m:
                parsed.append(rp)
                comp(os.path.basename(dirpath), rp, replicas=int(m.group(1)))
        elif re.match(r"appsettings[\w.]*\.json$|application[\w-]*\.(ya?ml|properties)$|\.env[\w.]*$|settings[\w]*\.py$|config[\w.]*\.(ts|js|json)$", low) or low in ("ocelotconfig.json", "ocelot.json"):
            text = _read(p)
            unit = os.path.basename(dirpath) if os.path.basename(dirpath) not in ("config", "src", "resources", "main") else os.path.basename(os.path.dirname(os.path.dirname(dirpath)))
            for i, line in enumerate(text.splitlines(), 1):
                if not CONFIG_KEYS.search(line):
                    continue
                hm = re.search(r"(?i)(?:host|server|data source|hostname|hosts?|url|uri|connection(?:string)?)\s*[\"']?\s*[:=]\s*[\"']?(?:[a-z]+://)?(?:[^@\s\"',;/]+@)?([a-z][\w.-]*)", line)
                target = hm.group(1) if hm else None
                role = role_of(line)
                if role == "app" and not target:
                    continue
                key = (target or role).lower()
                if key in ("localhost", "127.0.0.1", "host.docker.internal"):
                    key = role + "@localhost"
                c = comp(key, rp, role=role)
                deps.append((unit, key, f"{rp}:{i}"))
            if low in ("ocelotconfig.json", "ocelot.json"):
                gw = comp(os.path.basename(dirpath), rp, role="gateway")
                for m in re.finditer(r'"Host"\s*:\s*"([^"]+)"', text):
                    deps.append((gw["name"], m.group(1), rp))
                    comp(m.group(1), rp)

    for src, dst, ev in deps:
        d = comps.get(dst.lower())
        if d is None:
            d = comp(dst, ev)
        if src.lower() != dst.lower():
            d["dependents"].add(src)
    out = []
    for c in comps.values():
        c["dependents"] = sorted(c["dependents"])
        c["dependent_count"] = len(c["dependents"])
        infra = c["role"] in ("database", "broker", "cache", "gateway", "search", "storage")
        c["single_instance"] = (c["replicas"] or 1) <= 1
        c["spof_candidate"] = infra and c["single_instance"] and c["dependent_count"] >= 1
        if c["role"] == "broker" and c["single_instance"]:
            c["notes"].append("single broker instance: every async flow stops and in-flight messages may be lost if it dies; check clustering/quorum queues or a managed broker")
        if c["role"] == "database" and c["single_instance"]:
            c["notes"].append("single database instance: confirm managed HA/replica outside the repo")
        if c["role"] == "app" and c["ports"] and any(re.match(r"^\d", p) for p in c["ports"]) and any(x["role"] == "gateway" for x in comps.values()):
            c["notes"].append("service publishes a host port while a gateway exists: reachable without passing the gateway?")
        out.append(c)
    out.sort(key=lambda c: (-int(c["spof_candidate"]), -c["dependent_count"], c["name"]))
    doc = {"root": root, "parsed_files": sorted(set(parsed)), "components": out,
           "spof_candidates": [c["name"] for c in out if c["spof_candidate"]],
           "summary": {"components": len(out), "spof_candidates": sum(1 for c in out if c["spof_candidate"]),
                       "by_role": {r: sum(1 for c in out if c["role"] == r) for r in sorted({c["role"] for c in out})}}}
    md = ["# Topology", "", f"Parsed: {', '.join(doc['parsed_files']) or 'no compose/k8s files found'}", "",
          "| Component | Role | Replicas | Dependents | SPOF candidate | Notes | Sources |", "|---|---|---|---|---|---|---|"]
    for c in out:
        md.append(f"| {c['name']} | {c['role']} | {c['replicas'] if c['replicas'] is not None else '?'} | {', '.join(c['dependents']) or '-'} | {'YES' if c['spof_candidate'] else ''} | {'; '.join(c['notes'])} | {', '.join(c['sources'][:3])} |")
    md += ["", "Replica counts come from repo files only; managed services (RDS, Azure SQL, Amazon MQ) may be replicated outside the repo - record that in not_checked."]
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2)
    if a.md:
        os.makedirs(os.path.dirname(os.path.abspath(a.md)) or ".", exist_ok=True)
        with open(a.md, "w", encoding="utf-8") as fh:
            fh.write("\n".join(md) + "\n")
    print("\n".join(md) if not (a.out or a.md) else json.dumps(doc["summary"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
