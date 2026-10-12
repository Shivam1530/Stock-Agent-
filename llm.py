"""Tiny LLM client (stdlib only). Providers: anthropic | openai (any OpenAI-compatible endpoint).

Env:
  LLM_PROVIDER   anthropic (default) | openai
  ANTHROPIC_API_KEY / OPENAI_API_KEY
  LLM_MODEL      model id (default per provider below)
  OPENAI_BASE_URL  default https://api.openai.com/v1
                   (Gemini free tier: https://generativelanguage.googleapis.com/v1beta/openai)
                   (Groq free tier:   https://api.groq.com/openai/v1)
  ANTHROPIC_BASE_URL default https://api.anthropic.com
"""
import json
import os
import urllib.request

DEFAULT_MODELS = {"anthropic": "claude-sonnet-5-5", "openai": "gpt-4o-mini"}


def complete(system: str, user: str, temperature: float = 0.2, max_tokens: int = 2000) -> str:
    provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
    model = os.getenv("LLM_MODEL", DEFAULT_MODELS[provider])
    if provider == "anthropic":
        url = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/") + "/v1/messages"
        headers = {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
                   "content-type": "application/json"}
        payload = {"model": model, "max_tokens": max_tokens, "temperature": temperature,
                   "system": system, "messages": [{"role": "user", "content": user}]}
    elif provider == "openai":
        url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/") + "/chat/completions"
        headers = {"authorization": "Bearer " + os.environ["OPENAI_API_KEY"], "content-type": "application/json"}
        payload = {"model": model, "temperature": temperature, "max_tokens": max_tokens,
                   "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    else:
        raise SystemExit(f"Unknown LLM_PROVIDER {provider!r}")
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.load(r)
    if provider == "anthropic":
        return "".join(b.get("text", "") for b in data["content"])
    return data["choices"][0]["message"]["content"]
