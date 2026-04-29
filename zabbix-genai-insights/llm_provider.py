"""
Multi-provider LLM abstraction layer.
Supports: Google Gemini, OpenAI (GPT), DeepSeek, Ollama (local models).

Each provider implements the LLMProvider interface, allowing the core engine
to switch between models via environment variables without code changes.
"""

import os
from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Abstract base class for all LLM providers."""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Send a prompt and return the generated text response."""
        ...

    @abstractmethod
    def name(self) -> str:
        """Return a human-readable identifier for the provider/model."""
        ...


class GeminiProvider(LLMProvider):
    """Google Gemini provider using the google-generativeai SDK."""

    def __init__(self, api_key: str, model: str = "gemini-pro"):
        import google.generativeai as genai

        if not api_key:
            raise ValueError("GOOGLE_API_KEY is required for the Gemini provider.")
        genai.configure(api_key=api_key)
        self._client = genai.GenerativeModel(model)
        self._model_name = model

    def generate(self, prompt: str) -> str:
        response = self._client.generate_content(prompt)
        return response.text

    def name(self) -> str:
        return f"gemini/{self._model_name}"


class OpenAIProvider(LLMProvider):
    """OpenAI-compatible provider (works with any OpenAI-compatible API)."""

    def __init__(self, api_key: str, model: str = "gpt-4o", base_url: str = None):
        from openai import OpenAI

        if not api_key:
            raise ValueError("API key is required for the OpenAI provider.")
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = OpenAI(**kwargs)
        self._model = model

    def generate(self, prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        return response.choices[0].message.content

    def name(self) -> str:
        return f"openai/{self._model}"


class DeepSeekProvider(OpenAIProvider):
    """DeepSeek provider — uses an OpenAI-compatible API at api.deepseek.com."""

    def __init__(self, api_key: str, model: str = "deepseek-chat"):
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY is required for the DeepSeek provider.")
        super().__init__(
            api_key=api_key,
            model=model,
            base_url="https://api.deepseek.com",
        )

    def name(self) -> str:
        return f"deepseek/{self._model}"


class OllamaProvider(LLMProvider):
    """Ollama provider for local models (no API key required)."""

    def __init__(self, model: str = "llama3", base_url: str = "http://localhost:11434"):
        import requests

        self._model = model
        self._base_url = base_url.rstrip("/")
        self._session = requests.Session()

    def generate(self, prompt: str) -> str:
        response = self._session.post(
            f"{self._base_url}/api/generate",
            json={"model": self._model, "prompt": prompt, "stream": False},
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["response"]

    def name(self) -> str:
        return f"ollama/{self._model}"


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

PROVIDERS = {
    "gemini": GeminiProvider,
    "openai": OpenAIProvider,
    "deepseek": DeepSeekProvider,
    "ollama": OllamaProvider,
}


def get_provider(provider_name: str = None) -> LLMProvider:
    """
    Resolve and instantiate the LLM provider from environment variables.

    Environment variables
    ---------------------
    LLM_PROVIDER : str
        One of: gemini, openai, deepseek, ollama.  Defaults to ``gemini``.
    LLM_MODEL : str
        Model name (provider-specific).  Falls back to ``GENAI_MODEL`` for
        backward compatibility.
    GOOGLE_API_KEY : str
        Required when LLM_PROVIDER=gemini.
    OPENAI_API_KEY : str
        Required when LLM_PROVIDER=openai.
    DEEPSEEK_API_KEY : str
        Required when LLM_PROVIDER=deepseek.
    OLLAMA_BASE_URL : str
        Base URL for a local Ollama instance (default http://localhost:11434).
    """
    provider = (provider_name or os.environ.get("LLM_PROVIDER", "gemini")).lower()
    model = os.environ.get("LLM_MODEL") or os.environ.get("GENAI_MODEL")

    if provider == "gemini":
        api_key = os.environ.get("GOOGLE_API_KEY")
        return GeminiProvider(api_key=api_key, model=model or "gemini-pro")

    if provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        return OpenAIProvider(api_key=api_key, model=model or "gpt-4o")

    if provider == "deepseek":
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        return DeepSeekProvider(api_key=api_key, model=model or "deepseek-chat")

    if provider == "ollama":
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        return OllamaProvider(model=model or "llama3", base_url=base_url)

    raise ValueError(
        f"Unknown LLM provider: '{provider}'. "
        f"Supported providers: {', '.join(PROVIDERS.keys())}"
    )
