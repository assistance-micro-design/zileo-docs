# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Evaluation offline du RAG sur le golden set.

Usage:
    uv run --frozen python3 scripts/eval_rag.py [--tool search_hybrid|search_semantic]
                                                 [--threshold 0.5] [--min-cosine 0.72]

Metriques produites:
  - recall@1: pour les questions precises/ambigues, le doc attendu est-il en top 1
  - recall@5: idem mais sur le top 5
  - mrr: Mean Reciprocal Rank
  - fpr (false_positive_rate): pour hors-domaine, taux de queries qui retournent > 0
  - mean_results: nombre moyen de chunks retournes
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import yaml


MCP_URL = "http://localhost:8000/mcp"

VALID_TOOLS = ("search_hybrid", "search_semantic")


def call_search(
    query: str,
    *,
    api_key: str,
    tool: str,
    top_k: int = 5,
    threshold: float | None = None,
    min_cosine: float | None = None,
) -> list[dict[str, Any]]:
    """Appelle le tool MCP de recherche (search_hybrid ou search_semantic)."""
    args: dict[str, Any] = {"query": query, "top_k": top_k}
    if tool == "search_semantic" and threshold is not None:
        args["score_threshold"] = threshold
    if tool == "search_hybrid" and min_cosine is not None:
        args["min_cosine_relevance"] = min_cosine

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool, "arguments": args},
    }
    req = urllib.request.Request(
        MCP_URL,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "X-API-Key": api_key},
    )
    # Rate limit MCP: 30/min -> sleep 2.2s
    time.sleep(2.2)
    try:
        resp = urllib.request.urlopen(req, timeout=30)
    except urllib.error.HTTPError as e:
        if e.code == 429:
            time.sleep(10)
            resp = urllib.request.urlopen(req, timeout=30)
        else:
            raise
    data = json.loads(resp.read())
    if "error" in data:
        raise RuntimeError(f"MCP error: {data['error']}")
    result = json.loads(data["result"]["content"][0]["text"])
    return result.get("results", [])


def evaluate(
    questions: list[dict[str, Any]],
    docs: dict[str, dict[str, Any]],
    *,
    api_key: str,
    tool: str,
    threshold: float | None,
    top_k: int = 5,
    min_cosine: float | None = None,
) -> dict[str, Any]:
    """Execute le golden set et calcule les metriques."""
    by_type: dict[str, list[dict[str, Any]]] = {"precise": [], "ambigue": [], "hors_domaine": []}
    details: list[dict[str, Any]] = []

    for q in questions:
        results = call_search(
            q["query"],
            api_key=api_key,
            tool=tool,
            top_k=top_k,
            threshold=threshold,
            min_cosine=min_cosine,
        )

        record: dict[str, Any] = {
            "id": q["id"],
            "type": q["type"],
            "query": q["query"],
            "n_results": len(results),
            "top_score": results[0]["score"] if results else 0.0,
        }

        if q["type"] == "hors_domaine":
            record["false_positive"] = len(results) > 0
        else:
            expected_filename = docs[q["expected_doc"]]["filename"]
            ranks = [
                i + 1 for i, r in enumerate(results) if r.get("doc_filename") == expected_filename
            ]
            record["rank_first_match"] = ranks[0] if ranks else None
            record["recall_at_1"] = bool(ranks) and ranks[0] == 1
            record["recall_at_5"] = bool(ranks) and ranks[0] <= 5
            record["reciprocal_rank"] = 1.0 / ranks[0] if ranks else 0.0

        by_type[q["type"]].append(record)
        details.append(record)

    # Agregats
    precise = by_type["precise"]
    ambigue = by_type["ambigue"]
    hors = by_type["hors_domaine"]

    summary: dict[str, Any] = {
        "config": {
            "tool": tool,
            "threshold": threshold,
            "min_cosine": min_cosine,
            "top_k": top_k,
        },
        "precise": {
            "n": len(precise),
            "recall@1": _avg(precise, "recall_at_1"),
            "recall@5": _avg(precise, "recall_at_5"),
            "mrr": _avg(precise, "reciprocal_rank"),
        },
        "ambigue": {
            "n": len(ambigue),
            "recall@1": _avg(ambigue, "recall_at_1"),
            "recall@5": _avg(ambigue, "recall_at_5"),
            "mrr": _avg(ambigue, "reciprocal_rank"),
        },
        "hors_domaine": {
            "n": len(hors),
            "fpr": _avg(hors, "false_positive"),
            "mean_n_results_when_fp": (
                sum(r["n_results"] for r in hors if r["false_positive"])
                / max(1, sum(1 for r in hors if r["false_positive"]))
            ),
        },
    }
    return {"summary": summary, "details": details}


def _avg(records: list[dict[str, Any]], key: str) -> float:
    if not records:
        return 0.0
    return sum(float(r.get(key, 0)) for r in records) / len(records)


def main() -> int:
    parser = argparse.ArgumentParser(description="Eval RAG offline")
    parser.add_argument(
        "--tool",
        choices=VALID_TOOLS,
        default="search_hybrid",
        help="Tool MCP a evaluer (search_hybrid ou search_semantic)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="score_threshold (search_semantic uniquement, defaut 0.7 cote tool)",
    )
    parser.add_argument(
        "--min-cosine",
        type=float,
        default=None,
        help="min_cosine_relevance (search_hybrid uniquement, garde-fou cosinus)",
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--api-key", default=None, help="X-API-Key (sinon depuis env)")
    parser.add_argument(
        "--golden",
        default="tests/eval/golden_questions.yml",
        help="Chemin vers le golden set",
    )
    parser.add_argument("--json", action="store_true", help="Output JSON only")
    args = parser.parse_args()

    api_key = args.api_key
    if not api_key:
        api_key = os.environ.get("API_KEY", "")
    if not api_key:
        print("ERROR: --api-key ou API_KEY env requis", file=sys.stderr)
        return 1

    golden_path = Path(args.golden)
    with golden_path.open() as f:
        data = yaml.safe_load(f)

    result = evaluate(
        data["questions"],
        data["documents"],
        api_key=api_key,
        tool=args.tool,
        threshold=args.threshold,
        top_k=args.top_k,
        min_cosine=args.min_cosine,
    )

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    s = result["summary"]
    cfg = s["config"]
    print(
        f"\n=== Eval RAG | tool={cfg['tool']} threshold={cfg['threshold']} "
        f"min_cosine={cfg['min_cosine']} ===\n"
    )
    print(f"{'type':<14}{'n':>4}{'recall@1':>12}{'recall@5':>12}{'mrr':>8}{'fpr':>8}")
    print("-" * 60)
    for key in ("precise", "ambigue"):
        m = s[key]
        print(
            f"{key:<14}{m['n']:>4}{m['recall@1']:>12.2%}{m['recall@5']:>12.2%}{m['mrr']:>8.2f}{'':>8}"
        )
    h = s["hors_domaine"]
    print(f"{'hors_domaine':<14}{h['n']:>4}{'':>12}{'':>12}{'':>8}{h['fpr']:>8.2%}")
    print()
    print("Details des faux positifs hors_domaine:")
    for r in result["details"]:
        if r["type"] == "hors_domaine" and r.get("false_positive"):
            print(
                f"  [{r['id']}] '{r['query'][:50]}' -> {r['n_results']} resultats, top={r['top_score']:.3f}"
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
