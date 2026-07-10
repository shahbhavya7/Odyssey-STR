"""Application settings, loaded from environment variables (.env).

No secrets live in code: everything configurable comes through here.
The LLM provider is switchable — develop against local Ollama (free),
flip one env var to OpenAI for the final demo.
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _as_bool(value: str) -> bool:
    """Interpret common truthy strings ('true', '1', 'yes') as True."""
    return value.strip().lower() in {"true", "1", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    """All runtime configuration, read once from the environment."""

    # Which LLM backend to use: "ollama" (local, free) or "openai".
    provider: str = os.getenv("PROVIDER", "ollama").strip().lower()

    # Ollama (local, OpenAI-compatible endpoint).
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
    def active_model(self) -> str:
        """The model name for the currently selected provider."""
        return self.ollama_model if self.provider == "ollama" else self.openai_model

    @property
    def use_mock(self) -> bool:
        """True when the app should run without calling a real model.

        Mock mode is on if explicitly requested, or if we're on OpenAI with
        no API key. Ollama needs no key, so an empty OpenAI key does NOT
        force mock mode while PROVIDER=ollama — the app always has a way to run.
        """
        if self.mock_mode:
            return True
        return self.provider == "openai" and not self.openai_api_key


settings = Settings()
