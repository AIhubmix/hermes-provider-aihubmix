"""Offline tests for the AIHubMix provider profile."""

from __future__ import annotations

import io
import json
import sys
import unittest
import urllib.request
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from conftest_stub import (  # noqa: E402
    LEGACY_SUPER_MARKER,
    REPO_ROOT,
    SUPER_MARKER,
    load_plugin,
)


class _FakeResponse(io.BytesIO):
    """Context-manager byte stream standing in for an HTTP response."""

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()
        return False


def _stub_http(module, payload=None, *, error: Exception | None = None):
    """Point the plugin's credentialed fetch at a canned payload or failure."""
    calls: list[str] = []

    def fake_open(req, timeout=8.0):
        calls.append(req.full_url)
        if error is not None:
            raise error
        return _FakeResponse(json.dumps(payload).encode())

    sys.modules["hermes_cli.urllib_security"].open_credentialed_url = fake_open
    return calls


CATALOG = {
    "data": [
        {"model_id": "claude-sonnet-5", "features": "thinking,tools,function_calling"},
        {"model_id": "claude-opus-5", "features": "thinking,tools,structured_outputs"},
        {"model_id": "kimi-k3", "features": "thinking,function_calling"},
        {"model_id": "text-embedding-3-large", "features": "structured_outputs"},
        {"model_id": "some-chat-only", "features": ""},
        {"model_id": "claude-sonnet-5", "features": "tools"},  # duplicate
        {"model_id": "no-features-key"},
        "not-a-dict",
    ]
}


class ProfileDeclarationTests(unittest.TestCase):
    def setUp(self):
        self.module, self.profile = load_plugin()

    def test_registers_under_canonical_id(self):
        self.assertEqual(self.profile.name, "aihubmix")
        self.assertIn("aihub", self.profile.aliases)

    def test_endpoint_and_auth_declarations(self):
        self.assertEqual(self.profile.base_url, "https://aihubmix.com/v1")
        self.assertEqual(self.profile.hostname, "aihubmix.com")
        self.assertEqual(self.profile.auth_type, "api_key")
        self.assertEqual(self.profile.api_mode, "chat_completions")

    def test_env_vars_key_first_then_base_url_override(self):
        # Hermes treats a trailing *_BASE_URL entry as the user override.
        self.assertEqual(
            self.profile.env_vars, ("AIHUBMIX_API_KEY", "AIHUBMIX_BASE_URL")
        )

    def test_no_attribution_headers(self):
        # AIHubMix ships no referral/tracking headers, and Hermes forbids
        # un-gated outbound attribution.
        self.assertEqual(self.profile.default_headers, {})

    def test_fallback_models_are_unique_and_nonempty(self):
        models = self.profile.fallback_models
        self.assertTrue(models)
        self.assertEqual(len(models), len(set(models)))

    def test_aux_model_is_declared(self):
        self.assertTrue(self.profile.default_aux_model)

    def test_plugin_manifest_agrees_with_profile(self):
        manifest = {}
        for line in (REPO_ROOT / "aihubmix" / "plugin.yaml").read_text().splitlines():
            if ":" in line and not line.startswith(" "):
                key, _, value = line.partition(":")
                manifest[key.strip()] = value.strip()
        self.assertEqual(manifest["kind"], "model-provider")
        self.assertEqual(manifest["description"], self.profile.description)


class AgenticFilterTests(unittest.TestCase):
    def setUp(self):
        self.module, self.profile = load_plugin()

    def test_tools_marker_alone_qualifies(self):
        self.assertTrue(self.module._agentic({"features": "thinking,tools"}))

    def test_function_calling_marker_alone_qualifies(self):
        self.assertTrue(self.module._agentic({"features": "function_calling"}))

    def test_non_agentic_features_rejected(self):
        self.assertFalse(self.module._agentic({"features": "structured_outputs,web"}))

    def test_missing_or_malformed_features_rejected(self):
        self.assertFalse(self.module._agentic({}))
        self.assertFalse(self.module._agentic({"features": None}))
        self.assertFalse(self.module._agentic({"features": ["tools"]}))


class FetchModelsTests(unittest.TestCase):
    def setUp(self):
        self.module, self.profile = load_plugin()
        self.module._CATALOG_CACHE = None

    def test_keeps_only_tool_capable_models_in_catalog_order(self):
        _stub_http(self.module, CATALOG)
        self.assertEqual(
            self.profile.fetch_models(api_key="k"),
            ["claude-sonnet-5", "claude-opus-5", "kimi-k3"],
        )

    def test_uses_capability_annotated_catalog_endpoint(self):
        calls = _stub_http(self.module, CATALOG)
        self.profile.fetch_models(api_key="k")
        self.assertEqual(calls, [self.module.CATALOG_URL])

    def test_result_is_cached_across_calls(self):
        calls = _stub_http(self.module, CATALOG)
        first = self.profile.fetch_models(api_key="k")
        second = self.profile.fetch_models(api_key="k")
        self.assertEqual(first, second)
        self.assertEqual(len(calls), 1)

    def test_custom_base_url_defers_to_inherited_fetch(self):
        calls = _stub_http(self.module, CATALOG)
        result = self.profile.fetch_models(
            api_key="k", base_url="https://proxy.internal.example.com/v1"
        )
        self.assertEqual(result, SUPER_MARKER)
        self.assertEqual(calls, [], "must not probe the AIHubMix catalog for a proxy")

    def test_default_base_url_passed_through_still_uses_catalog(self):
        # Callers pass base_url unconditionally, falling back to the profile
        # default when the user configured nothing. That is not a proxy.
        calls = _stub_http(self.module, CATALOG)
        self.profile.fetch_models(api_key="k", base_url="https://aihubmix.com/v1/")
        self.assertEqual(calls, [self.module.CATALOG_URL])

    def test_catalog_failure_falls_back_to_inherited_fetch(self):
        _stub_http(self.module, error=OSError("connection reset"))
        self.assertEqual(self.profile.fetch_models(api_key="k"), SUPER_MARKER)

    def test_malformed_catalog_falls_back_to_inherited_fetch(self):
        _stub_http(self.module, {"data": "not-a-list"})
        self.assertEqual(self.profile.fetch_models(api_key="k"), SUPER_MARKER)

    def test_zero_agentic_models_falls_back_to_inherited_fetch(self):
        _stub_http(self.module, {"data": [{"model_id": "x", "features": "web"}]})
        self.assertEqual(self.profile.fetch_models(api_key="k"), SUPER_MARKER)

    def test_failed_fetch_is_not_cached(self):
        _stub_http(self.module, error=OSError("down"))
        self.profile.fetch_models(api_key="k")
        self.assertIsNone(self.module._CATALOG_CACHE)


class LegacyHermesBuildTests(unittest.TestCase):
    """The plugin must survive a Hermes build older than its field set.

    A TypeError at import is swallowed by the plugin loader, so the provider
    would silently fail to register and the user would see "unknown provider"
    with nothing in the logs pointing here.
    """

    def setUp(self):
        self.module, self.profile = load_plugin(legacy=True)
        self.module._CATALOG_CACHE = None

    def test_registers_despite_missing_profile_fields(self):
        self.assertEqual(self.profile.name, "aihubmix")
        self.assertFalse(hasattr(self.profile, "supports_vision"))

    def test_fields_the_build_does_support_are_still_applied(self):
        self.assertEqual(self.profile.base_url, "https://aihubmix.com/v1")
        self.assertEqual(self.profile.default_aux_model, "gemini-3.5-flash-lite")
        self.assertTrue(self.profile.fallback_models)

    def test_fallback_omits_base_url_for_legacy_signature(self):
        _stub_http(self.module, error=OSError("catalog down"))
        # Passing base_url to the pre-base_url signature would raise TypeError
        # on exactly the path we reach only when something else already broke.
        self.assertEqual(
            self.profile.fetch_models(api_key="k"), LEGACY_SUPER_MARKER
        )

    def test_catalog_path_still_works_on_legacy_build(self):
        _stub_http(self.module, CATALOG)
        self.assertEqual(
            self.profile.fetch_models(api_key="k"),
            ["claude-sonnet-5", "claude-opus-5", "kimi-k3"],
        )


class UrlOpenerFallbackTests(unittest.TestCase):
    """Builds predating ``hermes_cli.urllib_security`` must still fetch."""

    def setUp(self):
        self.module, self.profile = load_plugin()
        self.module._CATALOG_CACHE = None
        self._saved = sys.modules.get("hermes_cli.urllib_security")

    def tearDown(self):
        if self._saved is not None:
            sys.modules["hermes_cli.urllib_security"] = self._saved

    def test_prefers_the_credential_safe_opener_when_present(self):
        self.assertIs(
            self.module._url_opener(),
            sys.modules["hermes_cli.urllib_security"].open_credentialed_url,
        )

    def test_falls_back_to_urllib_when_module_absent(self):
        sys.modules.pop("hermes_cli.urllib_security", None)
        self.assertIs(self.module._url_opener(), urllib.request.urlopen)


class SupportedKwargsTests(unittest.TestCase):
    def setUp(self):
        self.module, _ = load_plugin()

    def test_unknown_fields_are_dropped(self):
        @dataclass
        class Narrow:
            name: str = ""

        result = self.module._supported_kwargs(
            Narrow, {"name": "x", "invented_field": 1}
        )
        self.assertEqual(result, {"name": "x"})

    def test_known_fields_pass_through_unchanged(self):
        result = self.module._supported_kwargs(
            self.module.AIHubMixProfile, self.module.PROFILE_FIELDS
        )
        self.assertEqual(result, self.module.PROFILE_FIELDS)


if __name__ == "__main__":
    unittest.main()
