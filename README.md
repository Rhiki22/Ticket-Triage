# IT Ticket Triage (human in the loop)

A small Python tool that reads IT support tickets and decides, for each one, **what it is, how urgent it is, and who should handle it**. It never answers customers on its own: confident, routine tickets get a *draft* reply for a person to review, and anything uncertain or security-related is sent to a human.

Built to practise the combination I care about: automating repetitive support work (from my IT support experience) while keeping human judgment and accountability (from my MSc Cybersecurity studies). Standard library only, Python 3.8+.

> **Built with AI assistance (Claude).** I directed the design, ran and reviewed the code, and tested it. I can explain every rule.

## How it decides

| Route | When | What happens |
|---|---|---|
| `SECURITY-ESCALATION` | Security keywords (phishing, malware, unauthorized, compromised, ...) | Always a human. No draft is ever written. Priority is at least P2. |
| `HUMAN-REVIEW` | Low confidence, mixed signals, or priority P1 (possible outage) | A person decides. Can be exported as a redacted AI prompt. |
| `AUTO-DRAFT` | Confident, routine ticket | A draft reply marked `[DRAFT - review before sending]`. Nothing is sent. |

**Confidence** = how much evidence there is (capped at 1) x how clearly the top category beats the runner-up. One strong keyword gives 1.0, one weak keyword gives 0.5, a tie gives 0. Default threshold to auto-draft is 0.6 (`--threshold`).

## Quick start

```bash
python3 ticket_triage.py demo_tickets.csv
python3 -m unittest -v
python3 generate_tickets.py --set heldout                       # builds the held-out benchmark
python3 ticket_triage.py synthetic_data/heldout_tickets.csv
python3 evaluate.py score triage_output.csv synthetic_data/heldout_labels.csv
python3 ticket_triage.py synthetic_data/heldout_tickets.csv --no-sensitive-guard   # compare without the guard
```

The demo file is 12 hand-written tickets in the same column layout as the public dataset below. It exists only to try the tool, and the numbers from it mean nothing (I wrote the tickets knowing the rules).

## Using real public data

A public support-ticket dataset on Hugging Face, `nerofinal012/TicketingToolDataset`, is described as support tickets from January to July 2024 under the MIT license, with columns Ticket No., Title, Content, Status, Author and Age. Download the CSV into a folder named `real_data/` (it is git-ignored), check the file name and columns, then run:

```bash
python3 ticket_triage.py real_data/<file>.csv --out triage_output.csv --llm-batch review_queue.md
```

If the column names differ, use `--id-col`, `--title-col`, `--content-col`; the tool prints the available columns if one is missing. Check the data for personal information before sharing anything, and do not commit the data or outputs (the `.gitignore` covers the default names).

If the real file is not available to you, the synthetic benchmarks below let you measure the pipeline in the meantime.

## Measuring it honestly

The dataset has no ground-truth category labels, so I label a random sample by hand and score the tool against it:

```bash
python3 evaluate.py template triage_output.csv --n 30 --out labels.csv   # then fill in true_category
python3 evaluate.py score triage_output.csv labels.csv
```

It reports category accuracy, how many **auto-drafts had the wrong category**, and **security recall** (security tickets that were caught) listing every miss. Security recall and wrong auto-drafts matter more than overall accuracy, because a missed security ticket or a wrong auto-reply is the costly mistake.

## The AI step, with safeguards

`--llm-batch` writes only the `HUMAN-REVIEW` tickets as a prompt for an AI model (paste it into Claude or similar). Safeguards:
- **Redaction first:** emails, URLs, IPs and phone numbers are masked, and the Author column is never included.
- **Prompt-injection awareness:** the prompt states that ticket text is untrusted data and must never be treated as instructions.
- **No actions:** the model only suggests a category and whether a human is needed. People decide.

## Synthetic benchmarks: what they showed

Two labelled, seeded, **synthetic** sets, written by me with AI help, so results show how the pipeline behaves, not how it would do on real tickets. Both are deliberately hard: typos, vague tickets, security incidents described without security words, harmless tickets containing scary words, outages, mixed issues.

- **Main set** (`generate_tickets.py`, 280 tickets): used while building the tool.
- **Held-out set** (`generate_tickets.py --set heldout`, 260 tickets): different templates and wording, written separately and used only to measure. I ran it once and report what came out.

### Round 1: the baseline found a dangerous failure
On the main set (no guard), 6 security tickets got an **automatic draft reply**: all one scenario, a found USB stick, read as a routine hardware ticket. The keyword security rule caught only 41% of security tickets (14 of 34); 14 of the misses still reached a person because the rules were unsure, which is the "fail toward a human" design working partly by accident.

### Round 2: a sensitive-wording guard
Tickets mentioning credentials, verification codes, bank details, gift vouchers, removable media, "claiming to be", or activity the user did not do, are **never auto-drafted**; a person reads them. It is deliberately broad.

| | Main set (guard terms were informed by these failures, so not an unbiased test) | Held-out set, guard off | Held-out set, guard on |
|---|---|---|---|
| Auto-drafted | 102 of 280 (36%), was 108 | 63 of 260 (24%) | 51 of 260 (20%) |
| Wrong category among auto-drafts | 0 | 9 (14.3%) | 0 |
| Security tickets that got an automatic draft | **0, was 6** | 0 | 0 |
| Security tickets that reached a person | 34 of 34 | 36 of 36 | 36 of 36 |
| Security rule recall (keywords only) | 41% | 33% | 33% |

### How I read this honestly
- **Main set:** the guard removed the USB-stick failure. That is the target it was built for, so this number proves little.
- **Held-out set, security:** 0 unsafe drafts with or without the guard. Its disguised incidents mostly had no routine-looking keywords, so low confidence sent them to a person anyway. **The held-out set did not reproduce the USB-stick failure, so it does not show the guard generalises.** Safety there rested on low confidence, which is fragile.
- **Held-out set, wrong drafts (9 to 0):** this came from tickets like "Reset VPN credentials" being routed to a person. They were read as Network because of the word "VPN", when they were really Access requests. The guard fixed that by accident, not by understanding it. It also held back 3 correctly handled "USB port dead" tickets. The price of the guard was 12 fewer automated tickets.
- **The keyword security rule still misses every disguised incident** (33% recall = only the obvious ones). The guard and low confidence carry the safety, not the rule.

### What I would do next
Write a third set that specifically stresses the guard (incidents that look like routine tickets), add a second check on every auto-draft (for example an AI model reviewing it with a human sign-off), and compare the rules against an AI classifier on the same labels. Few templates are repeated many times in these sets, so treat counts as pointers, not statistics.

## Design decisions
- **Transparent rules first, AI second.** Every decision can be explained by a keyword and a score, which makes errors easy to diagnose and security decisions auditable.
- **Fail toward a human.** Ambiguity, ties, empty tickets, outages and sensitive wording all go to review. Safety is not left to one rule: security keywords, the sensitive guard, and low confidence each catch what the others miss.
- **Tests encode the safety rules:** security always escalates, a mixed-signal ticket is never auto-drafted, redaction removes identifiers, bad columns produce a clear error.

## Limitations
- **Keyword rules are crude.** They miss paraphrases and sarcasm, and are English-only.
- **Redaction is basic.** It does not remove personal names or free-text identifiers, so review outputs before sharing.
- **Security detection is keyword-based**, so disguised incidents can be missed (see the benchmark). 
- **The sensitive guard is broad**: it also holds back routine tickets such as "USB port dead" or "reset VPN credentials", so it costs automation.
- **Security keywords over-trigger** (for example, "virus scan finished" would escalate). That is deliberate: a false alarm costs a minute, a miss costs more.
- **Priority is guessed from wording**, not from impact or SLA data.
- **No learning.** Improving it means a labelled dataset and a proper evaluation, then comparing against an AI model.

## Files
`ticket_triage.py` triage and AI-prompt export - `evaluate.py` labelling and scoring - `generate_tickets.py` synthetic labelled benchmark - `test_ticket_triage.py`, `test_generator.py` 23 tests - `synthetic_data/` generated tickets and labels - `demo_tickets.csv`, `demo_output.csv`, `demo_review_queue.md` demo input and sample output

---
*Author: Ricardo Ken-Morrison - MSc Cybersecurity & Emerging Threats, Middlesex University Dubai*
