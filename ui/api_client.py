"""Thin HTTP client the Streamlit UI uses to talk to the API.

The UI holds no business logic — it only calls these functions and renders the
result. Every function raises a friendly ApiError (with a readable message) on a
connection problem or a non-2xx response, so the UI can show a clean st.error
instead of a traceback.
"""

import os

import requests
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
_TIMEOUT = 30  # seconds; routing can take a few seconds on a local model


class ApiError(Exception):
    """A user-readable API failure (connection refused, timeout, or non-2xx)."""


def _request(method: str, path: str, **kwargs) -> requests.Response:
    """Make one request, translating low-level failures into a friendly ApiError."""
    url = f"{API_BASE_URL}{path}"
    try:
        resp = requests.request(method, url, timeout=_TIMEOUT, **kwargs)
    except requests.exceptions.ConnectionError as err:
        raise ApiError(
            "Could not reach the API. Is it running on "
            f"{API_BASE_URL}? Start it with: uvicorn app.api:app --port 8000"
        ) from err
    except requests.exceptions.Timeout as err:
        raise ApiError("The API took too long to respond (timeout).") from err
    return resp


def _raise_for_status(resp: requests.Response) -> None:
    """Turn a non-2xx response into an ApiError carrying the server's detail."""
    if resp.status_code // 100 == 2:
        return
    try:
        detail = resp.json().get("detail", resp.text)
    except ValueError:
        detail = resp.text or f"HTTP {resp.status_code}"
    raise ApiError(f"API error {resp.status_code}: {detail}")


def get_health() -> dict:
    """Return the /health payload, or raise ApiError if the API is unreachable."""
    resp = _request("GET", "/health")
    _raise_for_status(resp)
    return resp.json()


def create_ticket(text: str) -> dict:
    """Route + save one ticket; returns the full TicketOut dict."""
    resp = _request("POST", "/tickets", json={"text": text})
    _raise_for_status(resp)
    return resp.json()


def get_ticket(ticket_id: int) -> dict | None:
    """Fetch one ticket by id. Returns None on 404, raises ApiError otherwise."""
    resp = _request("GET", f"/tickets/{ticket_id}")
    if resp.status_code == 404:
        return None
    _raise_for_status(resp)
    return resp.json()


def list_tickets(**filters) -> dict:
    """List tickets with optional filters. Returns {count, items}.

    Accepts: limit, offset, priority, team, category, needs_review, q.
    None/empty values are dropped so they aren't sent as blank query params.
    """
    params = {k: v for k, v in filters.items() if v not in (None, "", "All")}
    resp = _request("GET", "/tickets", params=params)
    _raise_for_status(resp)
    return resp.json()
