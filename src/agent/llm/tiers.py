from __future__ import annotations

import os
from enum import Enum

from pydantic import BaseModel


class ModelTier(str, Enum):
    CHEAP = "cheap"
    STRONG = "strong"


class ProviderName(str, Enum):
    OPENROUTER = "openrouter"
    GEMINI = "gemini"


class TierConfig(BaseModel):
    provider: ProviderName
    model: str


class LLMResponse(BaseModel):
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""


def _active_provider() -> ProviderName:
    raw = os.environ.get("LLM_PROVIDER", "openrouter").strip().lower()
    return ProviderName.GEMINI if raw == "gemini" else ProviderName.OPENROUTER


def _tier_config_map() -> dict[ModelTier, TierConfig]:
    provider = _active_provider()

    if provider == ProviderName.GEMINI:
        return {
            ModelTier.CHEAP: TierConfig(
                provider=ProviderName.GEMINI,
                model=os.environ.get("GEMINI_MODEL_CHEAP", "gemini-2.5-flash"),
            ),
            ModelTier.STRONG: TierConfig(
                provider=ProviderName.GEMINI,
                model=os.environ.get("GEMINI_MODEL_STRONG", "gemini-2.5-pro"),
            ),
        }

    return {
        ModelTier.CHEAP: TierConfig(
            provider=ProviderName.OPENROUTER,
            model=os.environ.get("OPENROUTER_MODEL_CHEAP", "google/gemini-2.5-flash"),
        ),
        ModelTier.STRONG: TierConfig(
            provider=ProviderName.OPENROUTER,
            model=os.environ.get("OPENROUTER_MODEL_STRONG", "anthropic/claude-sonnet-4.5"),
        ),
    }


def resolve_tier(tier: ModelTier) -> TierConfig:
    return _tier_config_map()[tier]
