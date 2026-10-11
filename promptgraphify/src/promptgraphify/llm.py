"""Optional LLM access (Layer B). Off unless the environment configures a provider.

* Provider and model come from environment variables only; the API key is never logged, never placed in an
  exception message, never written to graph.json and never sent anywhere except the configured endpoint.
* One implementation: any OpenAI-compatible ``/chat/completions`` endpoint (hosted, or a local server such as
  Ollama / LM Studio on loopback). The ``LlmAdapter`` protocol is the seam for other providers.
* Standard library only (``urllib``): no new dependency. Redirects are refused, because a redirect would forward
  the ``Authorization`` header to another host.
"""

from __future__ import annotations

import ipaddress
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Protocol

PROVIDER_OPENAI_COMPATIBLE = "openai-compatible"
DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_TIMEOUT_S = 30.0
MAX_RESPONSE_BYTES = 2_000_000
ENV_PREFIX = "PROMPTGRAPHIFY_LLM_"

_KEY_SHAPES = re.compile(r"(?i)\b(sk-[A-Za-z0-9_\-]{8,}|bearer\s+[A-Za-z0-9._\-]{8,})")


class LlmConfigError(ValueError):
    """The LLM environment variables are present but unusable. The message names the variable, not its value."""


class LlmError(Exception):
    """No usable answer from the provider (network, timeout, HTTP status, malformed response).
    The message is safe to show: it contains no key and no request text."""


class LlmAdapter(Protocol):
    name: str
    model: str
    endpoint: str  # host[:port] only: shown to the user so they know where the prompt text goes
    timeout_s: float  # the adapter's own deadline; Layer B adds a small margin as a watchdog

    def complete(self, system: str, user: str) -> str:
        """Return the model's text answer (expected to be one JSON object). Raise :class:`LlmError` on failure."""
        ...


def mask_secrets(text: str, secrets: Iterable[str | None] = ()) -> str:
    """Replace every known secret and anything shaped like an API key / bearer token with ``***``."""
    out = text
    for secret in secrets:
        if secret and len(secret) >= 4:
            out = out.replace(secret, "***")
    return _KEY_SHAPES.sub("***", out)


@dataclass(frozen=True)
class LlmSettings:
    provider: str
    base_url: str
    model: str
    api_key: str | None = field(repr=False)  # never printed, not even by a traceback or a debug log
    timeout_s: float

    @property
    def endpoint(self) -> str:
        return urllib.parse.urlsplit(self.base_url).netloc

    def public(self) -> dict[str, str]:
        """What may be shown or logged: never the key itself."""
        return {
            "provider": self.provider,
            "endpoint": self.endpoint,
            "model": self.model,
            "api_key": "set" if self.api_key else "not set",
        }

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> LlmSettings | None:
        """``None`` if no provider is configured (the default). Raises :class:`LlmConfigError` if one is, but badly."""
        env = os.environ if env is None else env
        provider = (env.get(ENV_PREFIX + "PROVIDER") or "").strip()
        if not provider:
            return None
        if provider != PROVIDER_OPENAI_COMPATIBLE:
            raise LlmConfigError(f"{ENV_PREFIX}PROVIDER must be {PROVIDER_OPENAI_COMPATIBLE!r}, got {provider!r}")
        model = (env.get(ENV_PREFIX + "MODEL") or "").strip()
        if not model:
            raise LlmConfigError(f"{ENV_PREFIX}MODEL is required when a provider is set")
        base_url = (env.get(ENV_PREFIX + "BASE_URL") or DEFAULT_BASE_URL).strip().rstrip("/")
        _check_base_url(base_url)
        raw_timeout = (env.get(ENV_PREFIX + "TIMEOUT_S") or "").strip()
        try:
            timeout = float(raw_timeout) if raw_timeout else DEFAULT_TIMEOUT_S
        except ValueError as exc:
            raise LlmConfigError(f"{ENV_PREFIX}TIMEOUT_S must be a number of seconds") from exc
        if not 0 < timeout <= 300:
            raise LlmConfigError(f"{ENV_PREFIX}TIMEOUT_S must be between 0 and 300 seconds")
        key = (env.get(ENV_PREFIX + "API_KEY") or "").strip() or None
        return cls(provider, base_url, model, key, timeout)


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _check_base_url(url: str) -> None:
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise LlmConfigError(f"{ENV_PREFIX}BASE_URL must be an http(s) URL with a host")
    if parts.username or parts.password:
        raise LlmConfigError(f"{ENV_PREFIX}BASE_URL must not contain credentials; use {ENV_PREFIX}API_KEY")
    if parts.scheme == "http" and not _is_loopback(parts.hostname):
        raise LlmConfigError(f"{ENV_PREFIX}BASE_URL must use https unless it points at this machine (loopback)")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):  # type: ignore[override]
        return None  # the 3xx surfaces as an HTTPError instead of being followed


class OpenAICompatibleAdapter:
    name = PROVIDER_OPENAI_COMPATIBLE

    def __init__(self, settings: LlmSettings, opener: urllib.request.OpenerDirector | None = None):
        self._s = settings
        self.model = settings.model
        self.endpoint = settings.endpoint
        self.timeout_s = settings.timeout_s
        self._opener = opener or urllib.request.build_opener(_NoRedirect)

    def _mask(self, text: str) -> str:
        return mask_secrets(text, [self._s.api_key])

    def complete(self, system: str, user: str) -> str:
        payload = {
            "model": self._s.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        headers = {"content-type": "application/json", "accept": "application/json"}
        if self._s.api_key:
            headers["authorization"] = f"Bearer {self._s.api_key}"
        request = urllib.request.Request(  # noqa: S310 - scheme restricted to http(s) in _check_base_url
            self._s.base_url + "/chat/completions", json.dumps(payload).encode("utf-8"), headers, method="POST"
        )
        try:
            with self._opener.open(request, timeout=self._s.timeout_s) as resp:  # noqa: S310
                raw = resp.read(MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as exc:
            if 300 <= exc.code < 400:
                raise LlmError("the provider answered with a redirect; redirects are not followed") from None
            raise LlmError(f"the provider returned HTTP {exc.code}{self._error_detail(exc)}") from None
        except TimeoutError:
            raise LlmError(f"the provider did not answer within {self._s.timeout_s:g} s") from None
        except (urllib.error.URLError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            raise LlmError(f"cannot reach the provider ({type(reason).__name__})") from None
        if len(raw) > MAX_RESPONSE_BYTES:
            raise LlmError("the provider's answer is larger than the allowed size")
        try:
            body = json.loads(raw.decode("utf-8"))
            content = body["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError):
            raise LlmError("the provider's answer does not have the expected shape") from None
        if not isinstance(content, str):
            raise LlmError("the provider's answer does not have the expected shape")
        return content

    def _error_detail(self, exc: urllib.error.HTTPError) -> str:
        try:
            message = json.loads(exc.read(4000).decode("utf-8", "replace"))["error"]["message"]
        except (ValueError, KeyError, TypeError, OSError):
            return ""
        return ": " + self._mask(str(message))[:200] if message else ""


def get_adapter(env: Mapping[str, str] | None = None) -> LlmAdapter | None:
    settings = LlmSettings.from_env(env)
    return OpenAICompatibleAdapter(settings) if settings else None
