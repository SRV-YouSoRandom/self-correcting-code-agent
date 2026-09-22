from __future__ import annotations

from dotenv import load_dotenv

from agent.llm.providers.gemini import GeminiProvider
from agent.llm.providers.openrouter import OpenRouterProvider
import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from agent.llm.tiers import LLMResponse, ModelTier, ProviderName, resolve_tier

load_dotenv()


class LLMClient:
    def __init__(self) -> None:
        self._providers: dict[ProviderName, object] = {}

    def _get_provider(self, name: ProviderName):
        if name not in self._providers:
            if name == ProviderName.OPENROUTER:
                self._providers[name] = OpenRouterProvider()
            else:
                self._providers[name] = GeminiProvider()
        return self._providers[name]

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException, httpx.ConnectError)),
        stop=stop_after_attempt(6),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    async def generate(
        self,
        prompt: str,
        tier: ModelTier = ModelTier.CHEAP,
        system_prompt: str | None = None,
    ) -> LLMResponse:
        tier_config = resolve_tier(tier)
        provider = self._get_provider(tier_config.provider)
        return await provider.generate(
            model=tier_config.model,
            prompt=prompt,
            system_prompt=system_prompt,
        )
