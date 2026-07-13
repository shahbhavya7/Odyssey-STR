"""Manual baseline: time a human triaging tickets by hand.

Run this once, honestly, with the sample tickets. It shows each ticket, waits
for you to type category + team + priority, and times how long you take. The
result is a *defensible* manual number for the before/after comparison — not a
guess. Nothing here calls the model or the database.

Usage:
    python scripts/manual_baseline.py            # times up to 10 tickets
    python scripts/manual_baseline.py --n 20     # times up to 20 tickets

Saves data/manual_baseline.json:
    {"avg_seconds_per_ticket": 41.2, "n": 10, "measured_at": "2026-07-13T15:04:00"}
"""

import argparse
import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_CSV = ROOT / "data" / "sample_tickets.csv"
OUT_JSON = ROOT / "data" / "manual_baseline.json"


def load_tickets(path: Path) -> list[str]:
    """Read the 'text' column from the sample CSV. Returns [] on any problem."""
    if not path.exists():
        print(f"Sample file not found: {path}")
        print("Expected data/sample_tickets.csv (columns: id, text).")
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None or "text" not in reader.fieldnames:
            print("CSV must have a 'text' column.")
            return []
        return [row["text"].strip() for row in reader if row.get("text", "").strip()]


def run_exercise(tickets: list[str]) -> tuple[float, int]:
    """Show each ticket, time the human's answer. Returns (total_seconds, count)."""
    total = 0.0
    done = 0
    print("\nManual triage baseline")
    print("For each ticket, decide category + team + priority, type your answer, ")
    print("and press Enter. Type 'q' then Enter to stop early.\n")
    for i, ticket in enumerate(tickets, start=1):
        print(f"── Ticket {i}/{len(tickets)} " + "─" * 40)
        print(ticket)
        start = time.perf_counter()
        answer = input("your triage (category / team / priority): ").strip()
        elapsed = time.perf_counter() - start
        if answer.lower() == "q":
            print("Stopping early.")
            break
        total += elapsed
        done += 1
        print(f"  ⏱  {elapsed:.1f}s\n")
    return total, done


def main() -> int:
    """Entry point: run the timed exercise and save the baseline JSON."""
    parser = argparse.ArgumentParser(description="Time a human triaging tickets.")
    parser.add_argument("--n", type=int, default=10, help="max tickets to time")
    args = parser.parse_args()

    tickets = load_tickets(SAMPLE_CSV)
    if not tickets:
        return 1
    tickets = tickets[: max(1, args.n)]

    try:
        total, done = run_exercise(tickets)
    except (KeyboardInterrupt, EOFError):
        print("\nInterrupted — nothing saved.")
        return 1

    if done == 0:
        print("No tickets timed — nothing saved.")
        return 1

    avg = total / done
    result = {
        "avg_seconds_per_ticket": round(avg, 1),
        "n": done,
        "measured_at": datetime.now().isoformat(timespec="seconds"),
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print("─" * 56)
    print(f"Timed {done} ticket(s).")
    print(f"Total: {total:.1f}s   Average: {avg:.1f}s/ticket")
    print(f"Saved → {OUT_JSON.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
