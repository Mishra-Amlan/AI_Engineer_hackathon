from __future__ import annotations
import asyncio
from typing import Protocol
import httpx
from .types import ProviderError, ProviderResult, Usage, Message


class Provider(Protocol):
    async def complete(self, model: str, messages: list[Message], max_tokens: int,
                       temperature: float, timeout_s: float, json_mode: bool) -> ProviderResult: ...


class OpenRouterProvider:
    def __init__(self, api_key: str, base_url: str = "https://openrouter.ai/api/v1",
                 app_title: str = "unreliable-assistant", client: httpx.AsyncClient | None = None):
        self._key, self._base, self._title = api_key, base_url.rstrip("/"), app_title
        self._client = client or httpx.AsyncClient()

    async def complete(self, model, messages, max_tokens, temperature, timeout_s, json_mode):
        body = {"model": model, "messages": [m.model_dump() for m in messages],
                "max_tokens": max_tokens, "temperature": temperature}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {self._key}", "X-Title": self._title}
        try:
            r = await self._client.post(f"{self._base}/chat/completions", json=body,
                                        headers=headers, timeout=timeout_s)
        except (httpx.TimeoutException, asyncio.TimeoutError):
            raise ProviderError("timeout")
        except httpx.HTTPError as e:
            raise ProviderError("server", type(e).__name__)
        sc = r.status_code
        if sc == 429: raise ProviderError("rate_limit")
        if sc in (401, 403): raise ProviderError("auth", str(sc))
        if sc == 402: raise ProviderError("budget", "provider credits exhausted")
        if sc in (400, 404): raise ProviderError("model_unavailable", str(sc))
        if sc >= 500: raise ProviderError("server", str(sc))
        try:
            data = r.json()
            if "error" in data and not data.get("choices"):
                code = (data["error"] or {}).get("code")
                raise ProviderError("rate_limit" if code == 429 else "server", f"embedded:{code}")
            text = data["choices"][0]["message"]["content"] or ""
            u = data.get("usage") or {}
            return ProviderResult(text=text, model=data.get("model", model),
                                  usage=Usage(prompt_tokens=u.get("prompt_tokens", 0),
                                              completion_tokens=u.get("completion_tokens", 0)))
        except ProviderError:
            raise
        except Exception:
            raise ProviderError("bad_output", "unparseable provider response")


class FakeProvider:
    """Scriptable provider for tests: per-model queue of results/exceptions or a callable."""
    def __init__(self, script: dict | None = None, default: str = "ok"):
        self.script = script or {}
        self.default = default
        self.calls: list[str] = []

    async def complete(self, model, messages, max_tokens, temperature, timeout_s, json_mode):
        self.calls.append(model)
        s = self.script.get(model)
        if callable(s): s = s(messages)
        if isinstance(s, list):
            s = s.pop(0) if s else self.default
        if isinstance(s, Exception): raise s
        text = self.default if s is None else s
        await asyncio.sleep(0)
        return ProviderResult(text=text, model=model, usage=Usage(prompt_tokens=50, completion_tokens=20))


class MultiProvider:
    """Dispatches by model-spec prefix: 'groq:<model>' -> Groq, otherwise OpenRouter.
    Router/breakers/budgets key on the full spec, so each provider fails independently."""
    def __init__(self, default: Provider, named: dict[str, Provider] | None = None):
        self.default, self.named = default, named or {}

    async def complete(self, model, messages, max_tokens, temperature, timeout_s, json_mode):
        prefix, sep, rest = model.partition(":")
        if sep and prefix in self.named:
            return await self.named[prefix].complete(rest, messages, max_tokens, temperature, timeout_s, json_mode)
        if sep and prefix not in self.named and prefix in ("groq",):
            raise ProviderError("auth", f"no credentials configured for provider '{prefix}'")
        return await self.default.complete(model, messages, max_tokens, temperature, timeout_s, json_mode)
