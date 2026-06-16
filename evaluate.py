"""
Northwind Expense Review — Evaluation Harness

Usage:
    python evaluate.py                                  # uses evaluation_dataset.json
    python evaluate.py --test-file path/to/cases.json
    python evaluate.py --test-file cases.json --verbose

Test case JSON format:
    [
        {
            "employee_id": "NW-04821",
            "receipt_path": "data/submissions/01_clean_denver/receipts/01_united_airlines.pdf",
            "expected_verdict": "compliant",
            "is_policy_question": false   // optional — for refusal rate metric
        },
        ...
    ]
"""

import argparse
import json
from pathlib import Path

from database import init_db, load_seed_employees, get_employee
from reviewer import review_receipt
from rag import is_policy_relevant


def evaluate(test_file: str, verbose: bool = False):
    init_db()
    load_seed_employees()

    test_path = Path(test_file)
    if not test_path.exists():
        print(f"ERROR: test file not found: {test_file}")
        return

    with open(test_path, "r", encoding="utf-8") as f:
        test_cases = json.load(f)

    total = len(test_cases)
    if total == 0:
        print("No test cases found.")
        return

    correct_verdicts = 0
    citation_count = 0
    faithful_citations = 0   # citation non-empty AND reasoning is non-trivial
    refusal_correct = 0
    refusal_total = 0
    errors = 0

    for i, case in enumerate(test_cases, 1):
        employee_id = case.get("employee_id", "")
        receipt_path = case.get("receipt_path", "")
        expected_verdict = case.get("expected_verdict", "").strip().lower()
        is_policy_q = case.get("is_policy_question", False)

        if verbose:
            print(f"\n[{i}/{total}] {receipt_path}")

        # ── Refusal rate metric ──
        if is_policy_q:
            refusal_total += 1
            relevant, score, _ = is_policy_relevant(receipt_path)
            if expected_verdict == "refused" and not relevant:
                refusal_correct += 1
            elif expected_verdict != "refused" and relevant:
                refusal_correct += 1
            if verbose:
                print(f"  Policy relevance score: {score:.3f}")
            continue

        # ── Verdict accuracy ──
        employee = get_employee(employee_id)
        if not employee:
            print(f"  SKIP: employee {employee_id} not found")
            errors += 1
            continue

        try:
            result = review_receipt(employee, receipt_path)
        except Exception as e:
            print(f"  ERROR: {e}")
            errors += 1
            continue

        predicted = result.get("verdict", "").strip().lower()
        policy_quote = result.get("policy_quote", "").strip()
        reasoning = result.get("reasoning", "").strip()

        if predicted == expected_verdict:
            correct_verdicts += 1

        # Citation presence
        if policy_quote:
            citation_count += 1

        # Faithfulness heuristic: both quote and reasoning are non-trivial
        if policy_quote and len(reasoning) > 20:
            faithful_citations += 1

        if verbose:
            status = "✓" if predicted == expected_verdict else "✗"
            print(f"  {status}  expected={expected_verdict}  got={predicted}")
            print(f"  quote={policy_quote[:80]!r}")

    # ── Results ──
    receipt_total = total - refusal_total - errors

    accuracy = correct_verdicts / receipt_total if receipt_total > 0 else 0
    citation_rate = citation_count / receipt_total if receipt_total > 0 else 0
    faithfulness = faithful_citations / receipt_total if receipt_total > 0 else 0
    refusal_rate = refusal_correct / refusal_total if refusal_total > 0 else None

    print("\n" + "=" * 40)
    print("Evaluation Results")
    print("=" * 40)
    print(f"Total cases          : {total}")
    print(f"Receipt cases        : {receipt_total}")
    print(f"Errors/skipped       : {errors}")
    print()
    print(f"Verdict Accuracy     : {accuracy:.2%}  ({correct_verdicts}/{receipt_total})")
    print(f"Citation Presence    : {citation_rate:.2%}  ({citation_count}/{receipt_total})")
    print(f"Citation Faithfulness: {faithfulness:.2%}  ({faithful_citations}/{receipt_total})")
    if refusal_rate is not None:
        print(f"Refusal Rate Accuracy: {refusal_rate:.2%}  ({refusal_correct}/{refusal_total})")
    print("=" * 40)

    return {
        "accuracy": accuracy,
        "citation_rate": citation_rate,
        "faithfulness": faithfulness,
        "refusal_rate": refusal_rate,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Northwind Expense Eval Harness")
    parser.add_argument(
        "--test-file",
        default="evaluation_dataset.json",
        help="Path to the JSON test-case file (default: evaluation_dataset.json)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print per-case results",
    )
    args = parser.parse_args()
    evaluate(args.test_file, verbose=args.verbose)
