"""Application settings, loaded from environment variables (.env).

No secrets live in code: everything configurable comes through here.
The LLM provider is switchable via one env var (PROVIDER), zero code change:
  - "groq"   — DEFAULT. Fast hosted Qwen inference, no local server needed.
  - "ollama" — local, free, offline (slower); great for private/benchmark use.
  - "openai" — hosted GPT models.
"""

import logging
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("ticket_router.config")


def _as_bool(value: str) -> bool:
    """Interpret common truthy strings ('true', '1', 'yes') as True."""
    return value.strip().lower() in {"true", "1", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    """All runtime configuration, read once from the environment."""

    # Which LLM backend to use: "groq" (default), "ollama", or "openai".
    provider: str = os.getenv("PROVIDER", "groq").strip().lower()

    # Groq (default): hosted, OpenAI-compatible endpoint, no local server.
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_model: str = os.getenv("GROQ_MODEL", "qwen/qwen3-32b")
    groq_base_url: str = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")

    # Ollama (alternative: local, OpenAI-compatible endpoint).
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")

    # OpenAI (used only when provider == "openai").
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Shared model behaviour.
    temperature: float = float(os.getenv("TEMPERATURE", "0"))
    max_retries: int = int(os.getenv("MAX_RETRIES", "2"))
    mock_mode: bool = _as_bool(os.getenv("MOCK_MODE", "false"))
    max_input_chars: int = int(os.getenv("MAX_INPUT_CHARS", "6000"))

    # Database.
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/ticketrouter",
    )

    @property
    def is_serverless_db(self) -> bool:
        """True when DATABASE_URL points to Neon serverless Postgres."""
        return "neon.tech" in self.database_url.lower()

    @property
    def active_model(self) -> str:
        """The model name for the currently selected provider."""
        return {
            "groq": self.groq_model,
            "ollama": self.ollama_model,
            "openai": self.openai_model,
        }.get(self.provider, self.groq_model)

    @property
    def use_mock(self) -> bool:
        """True when the app should run without calling a real model.

        Mock mode is on if explicitly requested, or if the selected HOSTED provider
        has no API key (Groq or OpenAI). Ollama needs no key, so it never forces mock —
        the app always has a way to run.
        """
        if self.mock_mode:
            return True
        if self.provider == "groq" and not self.groq_api_key:
            return True
        if self.provider == "openai" and not self.openai_api_key:
            return True
        return False


settings = Settings()

# Visible (non-crashing) heads-up when the default provider has no key configured.
if settings.provider == "groq" and not settings.groq_api_key and not settings.mock_mode:
    logger.warning(
        "No GROQ_API_KEY set — falling back to mock mode. Set PROVIDER=ollama for "
        "local dev, or add a Groq key to .env."
    )
