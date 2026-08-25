#!/usr/bin/env python3
"""Check the curated fallback model list against the live AIHubMix catalog.

``fallback_models`` only appears when the live catalog is unreachable, so it
rots silently: a retired id sits in the picker for months and every pick spends
a round-trip 404ing. This script is the staleness gate — it fails when a
curated model has disappeared or stopped advertising tool support, and prints
current agentic flagships as replacement candidates.

Usage::

    AIHUBMIX_API_KEY=... python3 scripts/update_catalog.py

Exit status 0 = every curated id is live and tool-capable, 1 = drift found.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tests"))

from conftest_stub import load_plugin  # noqa: E402

TIMEOUT_SECONDS = 40


def fetch_catalog(api_key: str) -> list[dict]:
    req = urllib.request.Request("https://aihubmix.com/api/v1/models?types=llm")
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Accept", "application/json")
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
        payload = json.loads(resp.read().decode())
    entries = payload.get("data", [])
    if not isinstance(entries, list):
        raise SystemExit("unexpected catalog shape: 'data' is not a list")
    return [e for e in entries if isinstance(e, dict)]


def main() -> int:
    api_key = os.environ.get("AIHUBMIX_API_KEY", "").strip()
    if not api_key:
        print("AIHUBMIX_API_KEY is not set — cannot reach the catalog.")
        return 2

    module, profile = load_plugin()
    entries = fetch_catalog(api_key)
    by_id = {e["model_id"]: e for e in entries if isinstance(e.get("model_id"), str)}
    agentic = {mid for mid, e in by_id.items() if module._agentic(e)}

    print(f"catalog: {len(by_id)} models, {len(agentic)} tool-capable\n")

    curated = list(profile.fallback_models) + [profile.default_aux_model]
    drift = []
    for model_id in curated:
        if model_id not in by_id:
            drift.append((model_id, "RETIRED — absent from the catalog"))
        elif model_id not in agentic:
            features = by_id[model_id].get("features") or "(none)"
            drift.append((model_id, f"NO TOOL SUPPORT — features: {features}"))
        else:
            print(f"  ok       {model_id}")

    if not drift:
        print("\nAll curated models are live and tool-capable.")
        return 0

    print("\nDrift detected:")
    for model_id, reason in drift:
        print(f"  DRIFT    {model_id}: {reason}")

    print("\nCandidate replacements (tool-capable, newest catalog entries first):")
    for entry in sorted(
        (e for e in entries if e.get("model_id") in agentic),
        key=lambda e: e.get("created", 0),
        reverse=True,
    )[:20]:
        pricing = entry.get("pricing") or {}
        print(
            f"  {entry['model_id']:<40} "
            f"in={pricing.get('input')} out={pricing.get('output')} "
            f"ctx={entry.get('context_length')}"
        )
    print("\nEdit fallback_models in aihubmix/__init__.py, then re-run.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
