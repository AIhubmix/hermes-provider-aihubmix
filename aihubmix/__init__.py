"""AIHubMix provider profile for Hermes Agent.

Registers AIHubMix as the ``aihubmix`` provider over its OpenAI-compatible
Chat Completions endpoint. Everything else — credential resolution, the
``/model`` picker, ``hermes doctor``, the ``--provider`` flag — auto-wires
from the provider registry, so this plugin touches no core files.

Maintained by AIHubMix. No affiliate, referral, or attribution headers are
added to model requests.

Hermes core moves fast and a plugin has no say in which build a user runs, so
both points of contact with ``ProviderProfile`` — the fields we set and the
inherited ``fetch_models`` we delegate to — are resolved by introspection
rather than assumed. See ``_supported_kwargs`` and ``_inherited_fetch``.
"""

from __future__ import annotations

import dataclasses
import inspect
import json
import logging
import urllib.request
from typing import Any

from providers import register_provider
from providers.base import ProviderProfile

logger = logging.getLogger(__name__)

PROVIDER_ID = "aihubmix"
API_KEY_ENV = "AIHUBMIX_API_KEY"
BASE_URL_ENV = "AIHUBMIX_BASE_URL"

OPENAI_BASE_URL = "https://aihubmix.com/v1"
CATALOG_URL = "https://aihubmix.com/api/v1/models?types=llm"

# Catalog ``features`` markers that mean "this route accepts tool calls".
# AIHubMix fronts many upstream backends and their metadata is uneven — some
# entries advertise only ``tools`` (claude-opus-5, gpt-5.6-sol), others only
# ``function_calling``. Either marker qualifies; requiring both would hide
# roughly a third of the agentic catalog.
_AGENTIC_FEATURES = frozenset({"tools", "function_calling"})

_CATALOG_CACHE: list[str] | None = None


def _agentic(entry: dict[str, Any]) -> bool:
    """True when a catalog entry advertises tool-calling support."""
    raw = entry.get("features") or ""
    if not isinstance(raw, str):
        return False
    return bool(_AGENTIC_FEATURES & {part.strip() for part in raw.split(",")})


def _url_opener():
    """Return Hermes' credential-safe URL opener, or urllib's as a fallback.

    ``hermes_cli.urllib_security.open_credentialed_url`` guards a request that
    carries an Authorization header; builds predating that module fetch their
    own catalogs with a bare ``urllib.request.urlopen``. Falling back to the
    same call keeps the plugin working on those builds without ever being
    laxer than the host build is with its own credentialed catalog fetches.
    """
    try:
        from hermes_cli.urllib_security import open_credentialed_url

        return open_credentialed_url
    except ImportError:
        logger.debug(
            "aihubmix: this Hermes build has no urllib_security helper — "
            "using urllib.request.urlopen, as the build's own catalog fetch does"
        )
        return urllib.request.urlopen


def _supported_kwargs(cls: type, kwargs: dict[str, Any]) -> dict[str, Any]:
    """Drop profile fields the installed Hermes build does not define.

    ``ProviderProfile`` gains fields over time (``supports_vision`` and
    ``hostname`` are recent). Passing one to an older build raises TypeError
    at import, which the plugin loader swallows — the provider then silently
    fails to register and the user sees "unknown provider" with no cause.
    Declaring the full modern field set and filtering it to what this build
    accepts degrades to a slightly less capable profile instead.
    """
    try:
        known = {f.name for f in dataclasses.fields(cls)}
    except TypeError:  # pragma: no cover — non-dataclass profile base
        return dict(kwargs)
    dropped = sorted(set(kwargs) - known)
    if dropped:
        logger.debug(
            "aihubmix: this Hermes build has no profile field(s) %s — skipping",
            ", ".join(dropped),
        )
    return {k: v for k, v in kwargs.items() if k in known}


class AIHubMixProfile(ProviderProfile):
    """AIHubMix aggregator — tool-capable catalog filtering."""

    def fetch_models(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 8.0,
    ) -> list[str] | None:
        """Return tool-capable model ids from the AIHubMix catalog API.

        Hermes is an agent: a model that cannot call tools is dead weight in
        the picker. The plain ``/v1/models`` list carries no capability
        metadata, so prefer ``/api/v1/models?types=llm``, which publishes a
        ``features`` string per model, and keep only agentic entries.

        Falls back to the inherited ``/v1/models`` fetch whenever the rich
        catalog is unreachable, malformed, or filters down to nothing — a
        degraded picker beats an empty one.

        A caller-supplied ``base_url`` that differs from the default means the
        user pointed Hermes at a proxy or a self-hosted relay. Its catalog is
        not ours to interpret, so defer to the generic path in that case.
        """
        global _CATALOG_CACHE  # noqa: PLW0603

        caller_base = (base_url or "").strip()
        custom_base = bool(caller_base) and (
            caller_base.rstrip("/") != self.base_url.rstrip("/")
        )
        if custom_base:
            return self._inherited_fetch(
                api_key=api_key, base_url=base_url, timeout=timeout
            )

        if _CATALOG_CACHE is not None:
            return _CATALOG_CACHE

        models = self._fetch_agentic_catalog(api_key=api_key, timeout=timeout)
        if models:
            _CATALOG_CACHE = models
            return models

        return self._inherited_fetch(
            api_key=api_key, base_url=base_url, timeout=timeout
        )

    def _inherited_fetch(
        self, *, api_key: str | None, base_url: str | None, timeout: float
    ) -> list[str] | None:
        """Call the base-class fetch, passing only arguments it accepts.

        ``base_url`` was added to the base signature after this plugin's
        contract was written. Passing it to an older build is a TypeError, and
        the fallback path is exactly where a crash is least affordable — we
        are already here because the primary catalog failed.
        """
        parent = super()
        kwargs: dict[str, Any] = {"api_key": api_key, "timeout": timeout}
        try:
            accepted = inspect.signature(parent.fetch_models).parameters
        except (TypeError, ValueError):  # pragma: no cover — C-level callable
            accepted = {}
        if "base_url" in accepted:
            kwargs["base_url"] = base_url
        return parent.fetch_models(**kwargs)

    def _fetch_agentic_catalog(
        self, *, api_key: str | None, timeout: float
    ) -> list[str] | None:
        """Fetch and filter the capability-annotated catalog, or None."""
        open_url = _url_opener()

        req = urllib.request.Request(CATALOG_URL)
        if api_key:
            req.add_header("Authorization", f"Bearer {api_key}")
        req.add_header("Accept", "application/json")
        for key, value in self.default_headers.items():
            req.add_header(key, value)

        try:
            with open_url(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode())
        except Exception as exc:
            logger.debug("fetch_models(aihubmix): catalog API failed: %s", exc)
            return None

        entries = payload.get("data") if isinstance(payload, dict) else payload
        if not isinstance(entries, list):
            logger.debug("fetch_models(aihubmix): unexpected catalog shape")
            return None

        seen: set[str] = set()
        models: list[str] = []
        for entry in entries:
            if not isinstance(entry, dict) or not _agentic(entry):
                continue
            model_id = entry.get("model_id") or entry.get("id")
            if isinstance(model_id, str) and model_id and model_id not in seen:
                seen.add(model_id)
                models.append(model_id)

        if not models:
            logger.debug("fetch_models(aihubmix): catalog filtered to zero models")
            return None
        return models


PROFILE_FIELDS: dict[str, Any] = {
    "name": PROVIDER_ID,
    "aliases": ("aihub",),
    "display_name": "AIHubMix",
    "description": "AIHubMix — unified API for 400+ models (OpenAI-compatible)",
    "signup_url": "https://aihubmix.com/token",
    "env_vars": (API_KEY_ENV, BASE_URL_ENV),
    "base_url": OPENAI_BASE_URL,
    "hostname": "aihubmix.com",
    "auth_type": "api_key",
    "api_mode": "chat_completions",
    # AIHubMix relays OpenAI-compatible multimodal content, including images
    # inside tool-result messages, to whichever upstream serves the model.
    "supports_vision": True,
    # Cheap, 1M-context, vision-capable, tool-capable — suits compression,
    # title generation, and vision auxiliary calls.
    "default_aux_model": "gemini-3.5-flash-lite",
    # Shown only when the live catalog is unreachable. Flagship tool-capable
    # models spanning the vendors AIHubMix fronts; verified against the live
    # catalog by ``scripts/update_catalog.py``.
    "fallback_models": (
        "claude-sonnet-5",
        "claude-opus-5",
        "claude-fable-5",
        "gpt-5.6-sol",
        "gemini-3.7-flash",
        "gemini-3.5-flash-lite",
        "deepseek-v4-pro",
        "glm-5.3",
        "kimi-k3",
        "qwen3.8-max",
    ),
}

aihubmix = AIHubMixProfile(**_supported_kwargs(AIHubMixProfile, PROFILE_FIELDS))

register_provider(aihubmix)
