# hermes-provider-aihubmix

Official [AIHubMix](https://aihubmix.com) model-provider plugin for
[Hermes Agent](https://github.com/NousResearch/hermes-agent).

It registers AIHubMix as the `aihubmix` provider over the OpenAI-compatible
Chat Completions endpoint, and keeps the `/model` picker filtered to models
that can actually call tools. It touches no Hermes core files — discovery,
credential resolution, `hermes doctor`, and the `--provider` flag all
auto-wire from the provider registry.

Maintained by AIHubMix. No affiliate, referral, or attribution headers are
added to model requests.

## Why this lives outside the Hermes tree

Hermes closes PRs that add third-party product integrations under `plugins/`
in the main repo — a coupling-and-maintenance decision, not a quality bar. The
standing policy lives in the Hermes repository's contributor-instructions file
and reads "No new third-party-product plugins in-tree" (June 2026), so search
that phrase for the current wording. Standalone plugin repos are the supported path,
and they need nothing special from core.

## Hermes version

**Required:** any Hermes build with the model-provider plugin system — the
plugin only needs `providers.register_provider` and `providers.base.ProviderProfile`.
There is deliberately no version pin.

**Verified on:** 0.15.1 and 0.20.5 — the same code, unmodified, across roughly
14,800 commits of core drift. The plugin introspects every contact point with
core rather than assuming a shape, so newer fields (`supports_vision`), newer
signatures (`fetch_models(base_url=...)`), and newer modules
(`hermes_cli.urllib_security`) are used when present and skipped when absent.

**Recommended:** run a recent Hermes. Not because this plugin needs it — older
builds carry their own unrelated bugs. On 0.15.1, for example, `hermes -z`
returns no response for *any* provider, bundled ones included; that is fixed
in current builds.

## Install

### Drop-in (recommended)

```bash
git clone https://github.com/AIhubmix/hermes-provider-aihubmix.git
mkdir -p ~/.hermes/plugins/model-providers
cp -r hermes-provider-aihubmix/aihubmix ~/.hermes/plugins/model-providers/aihubmix
```

Hermes scans `$HERMES_HOME/plugins/model-providers/` lazily on the first
provider lookup. The plugin is live in the next session — no restart hook, no
config edit.

### pip entry point

```bash
pip install git+https://github.com/AIhubmix/hermes-provider-aihubmix.git
```

Entry-point plugins are opt-in: Hermes only loads the ones named in the
`plugins.enabled` list, so add `aihubmix` there. The drop-in path has no such
gate, which is why it is the default recommendation.

## Set an API key

```bash
export AIHUBMIX_API_KEY="AIHUBMIX_XXX"
```

Get a key at <https://aihubmix.com/token>. `hermes setup` also picks the
variable up, and `hermes doctor` probes it against the live catalog.

## Use it

```bash
hermes --provider aihubmix --model claude-sonnet-5
```

Or pick a model interactively with `/model` after selecting AIHubMix.

## Model catalog

The picker is populated from AIHubMix's capability-annotated catalog:

```text
https://aihubmix.com/api/v1/models?types=llm
```

Hermes is an agent, so a model that cannot call tools is dead weight in the
picker. Only entries advertising `tools` or `function_calling` are listed.
Either marker qualifies on its own — AIHubMix fronts many upstream backends
and their metadata is uneven, so requiring both would hide roughly a third of
the agentic catalog.

The plugin falls back to the plain `/v1/models` list whenever the annotated
catalog is unreachable, returns an unexpected shape, or filters down to zero
models. A degraded picker beats an empty one. If that fails too, a small
curated `fallback_models` tuple keeps offline starts usable.

### Pointing at a proxy

Set `AIHUBMIX_BASE_URL` to route through a proxy or self-hosted relay. When a
base URL other than the default is in play, the plugin stops interpreting the
AIHubMix catalog API and uses the generic `{base_url}/models` path instead —
someone else's relay does not owe us AIHubMix's response shape.

## Maintenance

The curated fallback list rots silently, because it only surfaces when the
live catalog is down. This gate catches that:

```bash
AIHUBMIX_API_KEY=... python3 scripts/update_catalog.py
```

It fails when a curated model has been retired or has stopped advertising
tool support, and prints current agentic flagships as replacement candidates.

## Development

```bash
python3 scripts/check_sensitive.py
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Tests run against stub `providers` / `hermes_cli` modules, so they need
neither a Hermes checkout nor network access.

All committed examples use `AIHUBMIX_XXX` placeholders. Never commit a real
key — start from `.env.example` and keep the populated file out of version
control. CI enforces this.

## License

MIT — see [LICENSE](LICENSE).
