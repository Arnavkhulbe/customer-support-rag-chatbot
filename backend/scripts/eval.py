#!/usr/bin/env python3
"""Repeatable RAG evaluation for the ShopSphere chatbot.

Sends every question in ``eval_dataset.json`` to the **live API**
(``POST /api/v1/chat``) and reports, per test:

* question
* expected source document (out-of-scope tests have none)
* whether the expected document appears in the retrieved results
* top retrieval score
* whether the final response is a grounded answer or the fallback refusal
* pass/fail

Pass criteria
-------------
* **In-scope** (expected document): the expected document must appear in
  ``sources`` **and** the answer must be grounded (not the fallback string).
* **Out-of-scope**: the response must be the fallback refusal (the chatbot
  must not answer from outside the knowledge base).

This script is read-only: it does not modify RAG logic, prompts, embeddings,
Pinecone configuration, frontend code, or PDFs, and it never ingests data.

Usage
-----
    # backend must already be running, e.g.:
    #   cd backend && HF_HUB_OFFLINE=1 .venv/Scripts/python -m uvicorn app.main:app --port 8000
    cd backend
    .venv/Scripts/python scripts/eval.py
    .venv/Scripts/python scripts/eval.py --base-url http://localhost:8000 --json results.json

Exit code is 0 when every test passes, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# Kept in sync with NO_CONTEXT_FALLBACK in app/rag/generator.py (verbatim).
FALLBACK_ANSWER = (
    "I couldn't find this information in the available ShopSphere company documents."
)

DATASET_PATH = Path(__file__).with_name("eval_dataset.json")


def ask_api(base_url: str, question: str, timeout: float) -> dict:
    """POST a question to the live chat endpoint and return the JSON response."""
    payload = json.dumps({"question": question}).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/v1/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def is_fallback(answer: str) -> bool:
    """True when the response is the fixed refusal string (or starts with it)."""
    text = (answer or "").strip()
    return text == FALLBACK_ANSWER or text.startswith(FALLBACK_ANSWER)


def evaluate(base_url: str, timeout: float) -> list[dict]:
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    rows: list[dict] = []

    cases = [("in_scope", c) for c in dataset.get("in_scope", [])] + [
        ("out_of_scope", c) for c in dataset.get("out_of_scope", [])
    ]

    for kind, case in cases:
        question = case["question"]
        expected = case.get("expected_document")
        started = time.time()
        try:
            data = ask_api(base_url, question, timeout)
        except (urllib.error.URLError, OSError) as exc:
            rows.append(
                {
                    "id": case["id"],
                    "kind": kind,
                    "question": question,
                    "expected_document": expected,
                    "expected_in_sources": None,
                    "top_score": None,
                    "response_type": f"ERROR: {exc}",
                    "passed": False,
                    "elapsed_s": round(time.time() - started, 2),
                }
            )
            continue

        sources = data.get("sources") or []
        retrieved_docs = [s.get("document") for s in sources]
        top_score = data.get("score")
        if top_score is None and sources:
            top_score = sources[0].get("score")

        grounded = not is_fallback(data.get("answer", ""))

        if kind == "in_scope":
            in_sources = expected in retrieved_docs
            passed = bool(in_sources and grounded)
            response_type = "grounded" if grounded else "fallback"
        else:
            in_sources = None  # n/a for out-of-scope
            passed = not grounded  # must refuse
            response_type = "fallback" if not grounded else "grounded"

        rows.append(
            {
                "id": case["id"],
                "kind": kind,
                "question": question,
                "expected_document": expected,
                "expected_in_sources": in_sources,
                "top_score": round(top_score, 4) if isinstance(top_score, (int, float)) else None,
                "response_type": response_type,
                "passed": passed,
                "elapsed_s": round(time.time() - started, 2),
            }
        )

    return rows


def _fmt_cell(value, width: int) -> str:
    text = "-" if value is None else str(value)
    if len(text) > width:
        text = text[: width - 1] + "…"
    return text.ljust(width)


def print_report(rows: list[dict]) -> None:
    headers = {
        "id": 7,
        "question": 44,
        "expected_document": 25,
        "expected_in_sources": 8,
        "top_score": 9,
        "response_type": 10,
        "passed": 6,
    }
    header_line = "  ".join(name.ljust(width) for name, width in headers.items())
    print(header_line)
    print("-" * len(header_line))
    for row in rows:
        cells = []
        for name, width in headers.items():
            value = row[name]
            if name == "expected_in_sources" and value is not None:
                value = "yes" if value else "no"
            if name == "passed":
                value = "PASS" if value else "FAIL"
            cells.append(_fmt_cell(value, width))
        print("  ".join(cells))

    total = len(rows)
    passed = sum(1 for r in rows if r["passed"])
    in_rows = [r for r in rows if r["kind"] == "in_scope"]
    oos_rows = [r for r in rows if r["kind"] == "out_of_scope"]
    in_pass = sum(1 for r in in_rows if r["passed"])
    oos_pass = sum(1 for r in oos_rows if r["passed"])
    rate = (100.0 * passed / total) if total else 0.0
    in_rate = (100.0 * in_pass / len(in_rows)) if in_rows else 0.0
    oos_rate = (100.0 * oos_pass / len(oos_rows)) if oos_rows else 0.0
    scores = [r["top_score"] for r in in_rows if r["top_score"] is not None]
    avg = (sum(scores) / len(scores)) if scores else 0.0

    print()
    print(f"In-scope:      {in_pass}/{len(in_rows)} passed ({in_rate:.1f}%)")
    print(f"Out-of-scope:  {oos_pass}/{len(oos_rows)} passed ({oos_rate:.1f}%)")
    print(f"Avg top retrieval score (in-scope): {avg:.4f}")
    print(f"OVERALL PASS RATE: {passed}/{total} ({rate:.1f}%)")

    failures = [r for r in rows if not r["passed"]]
    if failures:
        print()
        print("Failures:")
        for r in failures:
            expected = r["expected_document"] or "n/a"
            print(
                f"  {r['id']}: {r['question']!r} "
                f"(expected={expected}, in_sources={r['expected_in_sources']}, "
                f"response={r['response_type']}, top_score={r['top_score']})"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the ShopSphere RAG evaluation against the live API.")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Live API base URL (default: http://localhost:8000)")
    parser.add_argument("--timeout", type=float, default=60.0, help="Per-request timeout in seconds")
    parser.add_argument("--json", metavar="PATH", help="Also write full results as JSON to PATH")
    args = parser.parse_args()

    # Fail fast if the API is unreachable before running the whole suite.
    try:
        with urllib.request.urlopen(f"{args.base_url.rstrip('/')}/health", timeout=5) as resp:
            health = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError) as exc:
        print(f"ERROR: API at {args.base_url} is not reachable: {exc}", file=sys.stderr)
        print("Start it first: cd backend && HF_HUB_OFFLINE=1 .venv/Scripts/python -m uvicorn app.main:app --port 8000", file=sys.stderr)
        return 2
    if health.get("status") != "ok":
        print(f"ERROR: /health returned {health!r}", file=sys.stderr)
        return 2

    rows = evaluate(args.base_url, args.timeout)
    print_report(rows)

    if args.json:
        Path(args.json).write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(f"\nJSON results written to {args.json}")

    return 0 if all(r["passed"] for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
