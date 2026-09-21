#!/usr/bin/env python3
"""Detect LLM SDKs, agent frameworks, vector stores, and guardrail libraries
in a repository, and write audit/llm-stack.json.

Usage:
    python detect_llm_stack.py <repo_root> [--write] [--force]

Standard library only. Marker-based: greps well-known manifest files for
known package names, and a few source files for import/using strings that
manifests don't capture (e.g. Python `import` lines, C# `using` lines).
"""
import json
import os
import re
import sys
from datetime import datetime, timezone

MANIFEST_NAMES = {
    "package.json", "requirements.txt", "pyproject.toml", "Pipfile",
    "*.csproj", "pom.xml", "build.gradle", "build.gradle.kts", "go.mod",
}

# category -> id -> list of marker substrings to look for in manifest text
MARKERS = {
    "llm_sdks": {
        "openai": ["\"openai\"", "openai==", "openai>=", "openai>", "<PackageReference Include=\"OpenAI\""],
        "anthropic": ["\"@anthropic-ai/sdk\"", "anthropic==", "anthropic>=", "Anthropic.SDK"],
        "google-genai": ["\"@google/generative-ai\"", "google-generativeai", "google-genai"],
        "mistralai": ["mistralai", "\"@mistralai/mistralai\""],
        "cohere": ["cohere==", "\"cohere\"", "Cohere.NET"],
        "ollama": ["\"ollama\"", "ollama=="],
        "bedrock": ["boto3", "aws-sdk-bedrock", "AWSSDK.BedrockRuntime"],
        "azure-openai": ["Azure.AI.OpenAI", "azure-ai-openai"],
    },
    "agent_frameworks": {
        "langchain": ["langchain==", "langchain>=", "\"langchain\"", "langchain-core"],
        "langgraph": ["langgraph==", "langgraph>=", "\"langgraph\""],
        "llama-index": ["llama-index", "llama_index"],
        "autogen": ["pyautogen", "autogen-agentchat", "\"autogen\""],
        "crewai": ["crewai==", "crewai>=", "\"crewai\""],
        "semantic-kernel": ["Microsoft.SemanticKernel", "semantic-kernel"],
        "pydantic-ai": ["pydantic-ai", "pydantic_ai"],
        "openai-agents": ["openai-agents", "\"@openai/agents\""],
        "langchain4j": ["langchain4j"],
        "spring-ai": ["spring-ai", "org.springframework.ai"],
        "haystack": ["farm-haystack", "haystack-ai"],
    },
    "vector_stores": {
        "pinecone": ["pinecone-client", "\"@pinecone-database/pinecone\"", "pinecone=="],
        "weaviate": ["weaviate-client", "\"weaviate-ts-client\""],
        "chroma": ["chromadb", "\"chromadb\""],
        "qdrant": ["qdrant-client", "\"@qdrant/js-client-rest\""],
        "pgvector": ["pgvector"],
        "milvus": ["pymilvus", "\"@zilliz/milvus2-sdk-node\""],
        "faiss": ["faiss-cpu", "faiss-gpu"],
    },
    "guardrails": {
        "nemo-guardrails": ["nemoguardrails"],
        "guardrails-ai": ["guardrails-ai", "\"guardrails\""],
        "llm-guard": ["llm-guard"],
        "rebuff": ["rebuff"],
        "presidio": ["presidio-analyzer"],
    },
}

AGENTIC_HINTS = {"langgraph", "autogen", "crewai", "openai-agents", "langchain4j", "semantic-kernel"}


def iter_manifest_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in {
            "node_modules", ".git", "bin", "obj", "dist", "build", "__pycache__", ".venv", "venv",
        }]
        for name in filenames:
            if name in {"package.json", "requirements.txt", "pyproject.toml", "Pipfile",
                        "pom.xml", "build.gradle", "build.gradle.kts", "go.mod"} or name.endswith(".csproj"):
                yield os.path.join(dirpath, name)


def scan(root):
    result = {cat: {} for cat in MARKERS}
    notes = []
    for path in iter_manifest_files(root):
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                text = fh.read()
        except OSError:
            continue
        rel = os.path.relpath(path, root)
        rel_dir = os.path.dirname(rel) or "."
        for cat, ids in MARKERS.items():
            for pkg_id, markers in ids.items():
                if any(m in text for m in markers):
                    entry = result[cat].setdefault(pkg_id, {"id": pkg_id, "evidence": [], "roots": set()})
                    entry["evidence"].append(rel)
                    entry["roots"].add(rel_dir)

    out = {}
    likely_agentic = False
    for cat, entries in result.items():
        out[cat] = []
        for pkg_id, entry in entries.items():
            entry["roots"] = sorted(entry["roots"])
            out[cat].append(entry)
            if pkg_id in AGENTIC_HINTS:
                likely_agentic = True
    if not any(out.values()):
        notes.append("no LLM/agent/vector-store/guardrail marker found - check for a raw HTTP client "
                     "call to a model provider before concluding this repo has no LLM feature")
    return out, likely_agentic, notes


def main():
    args = sys.argv[1:]
    force = "--force" in args
    write = "--write" in args
    positional = [a for a in args if not a.startswith("--")]
    if not positional:
        print("usage: detect_llm_stack.py <repo_root> [--write] [--force]", file=sys.stderr)
        sys.exit(2)
    root = os.path.abspath(positional[0])
    out_path = os.path.join(root, "audit", "llm-stack.json")

    if os.path.exists(out_path) and not force:
        with open(out_path, "r", encoding="utf-8") as fh:
            print(fh.read())
        return

    categories, likely_agentic, notes = scan(root)
    doc = {
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "root": root,
        "llm_sdks": categories["llm_sdks"],
        "agent_frameworks": categories["agent_frameworks"],
        "vector_stores": categories["vector_stores"],
        "guardrails": categories["guardrails"],
        "likely_agentic": likely_agentic,
        "notes": notes,
    }
    print(json.dumps(doc, indent=2))
    if write:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2)
    if notes:
        for n in notes:
            print(f"warning: {n}", file=sys.stderr)


if __name__ == "__main__":
    main()
