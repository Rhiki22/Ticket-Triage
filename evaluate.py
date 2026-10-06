#!/usr/bin/env python3
"""Measure the triage rules against tickets YOU label by hand.

  python evaluate.py template triage_output.csv --n 30 --out labels.csv
      -> writes a random sample for you to label (fill in true_category)
  python evaluate.py score triage_output.csv labels.csv
      -> accuracy, plus how many security tickets were caught or missed
"""
import argparse
import csv
import random
import sys
from collections import Counter
from ticket_triage import CATEGORIES


def read(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def score(predictions, labels):
    pred = {r["ticket_id"]: r for r in predictions}
    rows = [(l, pred[l["ticket_id"]]) for l in labels
            if (l.get("true_category") or "").strip() and l["ticket_id"] in pred]
    n = len(rows)
    if n == 0:
        return {"n": 0}
    correct = sum(l["true_category"].strip() == p["category"] for l, p in rows)
    sec_true = [(l, p) for l, p in rows if l["true_category"].strip() == "Security incident"]
    sec_caught = [x for x in sec_true if x[1]["route"] == "SECURITY-ESCALATION"]
    sec_pred = [x for x in rows if x[1]["route"] == "SECURITY-ESCALATION"]
    sec_pred_right = [x for x in sec_pred if x[0]["true_category"].strip() == "Security incident"]
    missed = [(l["ticket_id"], p["route"]) for l, p in sec_true if p["route"] != "SECURITY-ESCALATION"]
    return {"n": n, "accuracy": round(correct / n, 3),
            "security_total": len(sec_true), "security_recall": round(len(sec_caught) / len(sec_true), 3) if sec_true else None,
            "security_precision": round(len(sec_pred_right) / len(sec_pred), 3) if sec_pred else None,
            "security_missed": missed,
            "security_auto_drafted": sum(1 for _, r in missed if r == "AUTO-DRAFT"),
            "security_reached_human": len(sec_true) - sum(1 for _, r in missed if r == "AUTO-DRAFT"),
            "auto_draft_wrong": sum(p["route"] == "AUTO-DRAFT" and l["true_category"].strip() != p["category"] for l, p in rows),
            "auto_draft_total": sum(p["route"] == "AUTO-DRAFT" for _, p in rows),
            "human_review_total": sum(p["route"] == "HUMAN-REVIEW" for _, p in rows)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("template")
    t.add_argument("predictions")
    t.add_argument("--n", type=int, default=30)
    t.add_argument("--out", default="labels.csv")
    s = sub.add_parser("score")
    s.add_argument("predictions")
    s.add_argument("labels")
    a = ap.parse_args(argv)

    if a.cmd == "template":
        rows = read(a.predictions)
        sample = random.Random(1).sample(rows, min(a.n, len(rows)))
        with open(a.out, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["ticket_id", "title", "preview", "true_category"])
            for r in sample:
                w.writerow([r["ticket_id"], r["title"], r["preview"], ""])
        print(f"Wrote {len(sample)} tickets to {a.out}. Fill in true_category using exactly:\n  " + "\n  ".join(CATEGORIES))
        return 0
    res = score(read(a.predictions), read(a.labels))
    if res["n"] == 0:
        print("No labelled tickets found. Fill in the true_category column first.")
        return 2
    print(f"Labelled tickets scored: {res['n']}")
    print(f"Category accuracy: {res['accuracy']:.1%}")
    ad, adw = res["auto_draft_total"], res["auto_draft_wrong"]
    print(f"Auto-drafted: {ad} ({ad / res['n']:.0%} of tickets). Wrong category among them: {adw}"
          + (f" ({adw / ad:.1%})" if ad else ""))
    print(f"Sent to a human for review: {res['human_review_total']}")
    if res["security_total"]:
        print(f"Security tickets: {res['security_total']}  recall: {res['security_recall']:.0%}"
              + (f"  precision: {res['security_precision']:.0%}" if res['security_precision'] is not None else ""))
        print(f"  Reached a person (escalated or sent to review): {res['security_reached_human']} of {res['security_total']}")
        print(f"  UNSAFE - security tickets that got an automatic draft: {res['security_auto_drafted']}")
        for tid, route in res["security_missed"]:
            if route == "AUTO-DRAFT":
                print(f"    auto-drafted security ticket: {tid}")
    else:
        print("No security tickets in your labelled sample, so security recall is untested.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
