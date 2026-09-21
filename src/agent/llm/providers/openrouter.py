from __future__ import annotations

import os

import httpx

from agent.llm.tiers import LLMResponse

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterProvider:
    def __init__(self, api_key: str | None = None, timeout_seconds: float = 90.0) -> None:
        self._api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        if not self._api_key:
            raise ValueError("OPENROUTER_API_KEY is not set")
        self._timeout_seconds = timeout_seconds

    async def generate(self, model: str, prompt: str, system_prompt: str | None = None) -> LLMResponse:
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": model, "messages": messages}

        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            response = await client.post(OPENROUTER_API_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        choice = data["choices"][0]
        text = choice["message"]["content"]
        usage = data.get("usage", {})

        return LLMResponse(
            text=text,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            model=model,
        )
