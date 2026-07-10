"""Application settings, loaded from environment variables (.env).

No secrets live in code: everything configurable comes through here.
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

    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    model: str = os.getenv("MODEL", "gpt-4o-mini")
    temperature: float = float(os.getenv("TEMPERATURE", "0"))
    max_retries: int = int(os.getenv("MAX_RETRIES", "2"))
    mock_mode: bool = _as_bool(os.getenv("MOCK_MODE", "false"))
    max_input_chars: int = int(os.getenv("MAX_INPUT_CHARS", "6000"))
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/ticketrouter",
    )

    @property
    def use_mock(self) -> bool:
        """True when the app should run without calling OpenAI.

        Mock mode is on if explicitly requested, or if no API key is set —
        so the app always has a way to run instead of crashing.
        """
        return self.mock_mode or not self.openai_api_key


settings = Settings()
