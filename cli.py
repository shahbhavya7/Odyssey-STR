"""Terminal tester for the router.

Usage:
    python cli.py "my ticket text"   # route one ticket, print JSON
    python cli.py                    # interactive loop (Ctrl+C to quit)
"""

import json
import sys

from app.router_service import route_ticket


def _print_result(text: str) -> None:
    """Route one ticket and print the result as pretty JSON."""
    result = route_ticket(text)
    print(json.dumps(result, indent=2, ensure_ascii=False))


def main() -> None:
    """Route the CLI argument, or drop into an interactive loop if none given."""
    if len(sys.argv) > 1:
        _print_result(" ".join(sys.argv[1:]))
        return

    print("Smart Ticket Router — type a ticket and press Enter (Ctrl+C to quit).")
    try:
        while True:
            text = input("\nticket> ")
            _print_result(text)
    except (KeyboardInterrupt, EOFError):
        print("\nbye.")


if __name__ == "__main__":
    main()
