from __future__ import annotations

import os

import httpx

from agent.llm.tiers import LLMResponse

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiProvider:
    def __init__(self, api_key: str | None = None, timeout_seconds: float = 90.0) -> None:
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        if not self._api_key:
            raise ValueError("GEMINI_API_KEY is not set")
        self._timeout_seconds = timeout_seconds

    async def generate(self, model: str, prompt: str, system_prompt: str | None = None) -> LLMResponse:
        url = f"{GEMINI_API_BASE}/{model}:generateContent?key={self._api_key}"

        payload: dict = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        }
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            response = await client.post(url, json=payload)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                safe_url = str(exc.request.url).split("?")[0]
                raise httpx.HTTPStatusError(
                    f"{exc.response.status_code} error for {safe_url}",
                    request=exc.request,
                    response=exc.response,
                ) from None
            data = response.json()

        candidate = data["candidates"][0]
        parts = candidate["content"]["parts"]
        text = "".join(part.get("text", "") for part in parts)
        usage = data.get("usageMetadata", {})

        return LLMResponse(
            text=text,
            prompt_tokens=usage.get("promptTokenCount", 0),
            completion_tokens=usage.get("candidatesTokenCount", 0),
            model=model,
        )
