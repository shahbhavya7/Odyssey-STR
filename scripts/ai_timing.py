"""AI timing: route all sample tickets and measure how fast the router is.

Prefers the live API (so it exercises the full stack and persists rows), and
falls back to calling route_ticket() directly if the API is unreachable so
this always produces a number, even offline. Reports average processing_ms per
ticket and total time, and saves data/ai_timing.json for the UI's Time Saved card.

Usage:
    python scripts/ai_timing.py
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import csv  # noqa: E402

SAMPLE_CSV = ROOT / "data" / "sample_tickets.csv"
OUT_JSON = ROOT / "data" / "ai_timing.json"


def load_tickets(path: Path) -> list[str]:
    """Read the 'text' column from the sample CSV. Returns [] on any problem."""
    if not path.exists():
        print(f"Sample file not found: {path}")
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None or "text" not in reader.fieldnames:
            print("CSV must have a 'text' column.")
            return []
        return [row["text"].strip() for row in reader if row.get("text", "").strip()]


def _via_api(tickets: list[str]) -> list[int] | None:
    """Route every ticket through the running API. Returns per-ticket ms, or None."""
    try:
        import os

        import requests
        from dotenv import load_dotenv

        load_dotenv()
        base = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
        # Fail fast if the API isn't up.
        requests.get(f"{base}/health", timeout=3).raise_for_status()
    except Exception:
        return None

    per_ticket: list[int] = []
    for i, text in enumerate(tickets, start=1):
        resp = requests.post(f"{base}/tickets", json={"text": text}, timeout=60)
        resp.raise_for_status()
        per_ticket.append(int(resp.json().get("processing_ms") or 0))
        print(f"  routed {i}/{len(tickets)} via API")
    return per_ticket


def _via_service(tickets: list[str]) -> list[int]:
    """Route every ticket by calling route_ticket() directly (no API needed)."""
    from app.router_service import route_ticket

    per_ticket: list[int] = []
    for i, text in enumerate(tickets, start=1):
        result = route_ticket(text)
        per_ticket.append(int(result.get("processing_ms") or 0))
        print(f"  routed {i}/{len(tickets)} via route_ticket()")
    return per_ticket


def main() -> int:
    """Entry point: route all tickets, measure, and save the timing JSON."""
    tickets = load_tickets(SAMPLE_CSV)
    if not tickets:
        return 1

    print(f"Routing {len(tickets)} tickets…")
    wall_start = time.perf_counter()

    source = "api"
    per_ticket = _via_api(tickets)
    if per_ticket is None:
        print("API not reachable falling back to route_ticket() directly.")
        source = "service"
        try:
            per_ticket = _via_service(tickets)
        except Exception as err:  # noqa: BLE001 - report cleanly, never crash
            print(f"Routing failed: {type(err).__name__}: {err}")
            return 1

    wall = time.perf_counter() - wall_start
    n = len(per_ticket)
    avg_ms = sum(per_ticket) / n if n else 0.0

    result = {
        "avg_ms_per_ticket": round(avg_ms, 1),
        "total_ms": sum(per_ticket),
        "n": n,
        "source": source,
        "measured_at": datetime.now().isoformat(timespec="seconds"),
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print("─" * 56)
    print(f"Routed {n} tickets via {source} in {wall:.1f}s wall time.")
    print(f"Average model time: {avg_ms:.0f} ms/ticket")
    print(f"Saved → {OUT_JSON.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
