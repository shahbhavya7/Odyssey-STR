"""Which model configurations the benchmark harness compares.

Edit MODEL_CONFIGS to add/remove models. Each entry:
    {"name": <label>, "provider": "ollama"|"openai", "model": <exact model id>}

For Ollama, `model` must match a tag you have pulled (`ollama list`). For OpenAI,
the key comes from .env (OPENAI_API_KEY) — never hard-code it here.
"""

from __future__ import annotations

# ---- EDIT ME: the models to benchmark ---------------------------------------
# Groq (the app's DEFAULT provider) is first. The Ollama Qwen entries are kept on
# purpose — hosted-vs-local latency for the same model family is one of the most
# interesting comparisons. Configs you can't reach (no key / not pulled) are cleanly
# skipped, not errored.
MODEL_CONFIGS: list[dict[str, str]] = [
    {"name": "Llama 3.3 70B", "provider": "groq", "model": "llama-3.3-70b-versatile"},
    # {"name": "Qwen 7B (local)", "provider": "ollama", "model": "qwen2.5:7b"},
    # {"name": "Qwen 4B (local)", "provider": "ollama", "model": "qwen3:4b"},
    # {"name": "Qwen 14B (local)", "provider": "ollama", "model": "qwen2.5:14b"},
    {"name": "GPT-4o-mini", "provider": "openai", "model": "gpt-4o-mini"},
    {"name": "GPT-5-mini", "provider": "openai", "model": "gpt-5-mini"},
]
# -----------------------------------------------------------------------------


def ollama_available_models(base_url: str) -> set[str]:
    """Return the set of model tags Ollama has pulled, or empty set on any error.

    Uses Ollama's native /api/tags endpoint. Never raises — a missing/here-down
    Ollama just yields an empty set, and the runner reports the config as skipped.
    """
    import requests  # local import so importing this module stays dependency-light

    # base_url is the OpenAI-compatible URL (…/v1); strip to the host root.
    root = base_url.rstrip("/")
    if root.endswith("/v1"):
        root = root[: -len("/v1")]
    try:
        resp = requests.get(f"{root}/api/tags", timeout=5)
        resp.raise_for_status()
        return {m.get("name", "") for m in resp.json().get("models", [])}
    except Exception:
        return set()


def availability_note(
    config: dict[str, str],
    *,
    groq_key_present: bool,
    openai_key_present: bool,
    ollama_models: set[str] | None,
) -> str | None:
    """Return a reason to SKIP this config, or None if it should run.

    - Groq / OpenAI configs need a key (else "skipped: no API key").
    - Ollama configs should match a pulled tag; if we could list tags and it's not
      there, skip with a clear "not pulled" note. If we couldn't list tags (Ollama
      down), we still attempt — the run records failures as misses rather than
      pre-skipping, so a transient blip doesn't silently drop a model.
    """
    if config["provider"] == "groq" and not groq_key_present:
        return "skipped: no Groq API key (set GROQ_API_KEY in .env)"
    if config["provider"] == "openai" and not openai_key_present:
        return "skipped: no OpenAI API key (set OPENAI_API_KEY in .env)"
    if config["provider"] == "ollama" and ollama_models:
        if config["model"] not in ollama_models:
            return (
                f"skipped: Ollama model '{config['model']}' not pulled "
                f"(run: ollama pull {config['model']})"
            )
    return None
