# Repository Agent Instructions

This repo is a standalone Hermes Agent model-provider plugin. The following
invariants are mandatory — they are the reasons the plugin is accepted as a
good citizen of the Hermes ecosystem, not stylistic preferences.

## Security

- Every committed credential example stays in `AIHUBMIX_XXX` placeholder form.
  `python3 scripts/check_sensitive.py` enforces this and runs in CI.
- Never commit a populated `.env`.

## No un-gated outbound attribution

Do not add affiliate, referral, analytics, or attribution headers to model
requests. `default_headers` stays empty. Hermes' contribution rubric rejects
outbound usage attribution without a user-facing opt-in, and AIHubMix's own
provider plugins make the same promise. A test asserts this.

## No inferred model metadata

Do not fill missing catalog fields with guesses. When AIHubMix's catalog does
not advertise a capability, treat the model as not having it and let it drop
out of the list. Silently promoting a model into the picker on a guessed
capability produces a runtime 4xx the user cannot diagnose.

## One provider entry, chat_completions only

AIHubMix also exposes an Anthropic Messages endpoint at
`https://aihubmix.com/v1/messages`, and it accepts every model in the catalog,
not just Claude ones. Registering a second `anthropic_messages` profile for it
is therefore technically possible. Do not.

Hermes' own bundled aggregator plugins settle this: OpenRouter ships a single
`chat_completions` entry even though `https://openrouter.ai/api/v1/messages`
exists. The profiles that declare `api_mode="anthropic_messages"` — anthropic,
minimax — are first-party vendor APIs whose default route is already the
Anthropic protocol, not aggregators. The ecosystem convention is: aggregators
expose one OpenAI-compatible entry.

A second entry would also be indistinguishable from the first in the picker.
Both would list the same models over the same credentials, differing only in
wire protocol, which is not a distinction a user should have to make.

If native Messages support becomes worth having — prompt-cache accounting is
the plausible motivation — the right move is to ask upstream to open up
per-model wire selection as a profile hook. Hermes already does exactly this
for Nous Portal (`nous_api_mode(model)` in `agent/agent_init.py`), but it is
hardcoded in core with no plugin-facing equivalent. Get the hook, then use it.

## Stay out of Hermes core

The plugin declares a `ProviderProfile` and overrides documented hooks. If
something seems to need a Hermes core change, that is a signal to widen the
generic hook surface upstream — not to patch core from here, and not to
special-case this provider in a fork.

## Degrade, don't fail

Catalog fetches have three tiers: annotated catalog → plain `/v1/models` →
curated `fallback_models`. Keep it that way. Any new fetch path must fall
through rather than raise; an empty picker is worse than a stale one.

## Before opening a PR

```bash
python3 scripts/check_sensitive.py
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Run `AIHUBMIX_API_KEY=... python3 scripts/update_catalog.py` when touching
`fallback_models` or `default_aux_model`.
