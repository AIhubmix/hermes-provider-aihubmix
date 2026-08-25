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

## The version-tolerance code is not dead code

Three places introspect core instead of assuming its shape:

- `_supported_kwargs()` filters profile kwargs through `dataclasses.fields()`
- `_inherited_fetch()` passes only the kwargs `super().fetch_models` accepts
- `_url_opener()` imports `hermes_cli.urllib_security` behind a guard

On a current Hermes build all three take the modern branch, so they read like
no-ops. They are not. A published plugin cannot pin the Hermes build it is
installed into, and the failure mode when one of these is wrong is nasty: the
plugin loader swallows the import-time exception, the provider silently fails
to register, and the user sees "unknown provider" with nothing in the logs
pointing at the cause.

This was not theoretical. All three were found against a real 0.15.1 install
that lacked `supports_vision`, lacked `base_url` on `fetch_models`, and had no
`urllib_security` module at all. Tests cover both a modern and a legacy stub
profile — if you remove a branch, a legacy test fails. That is the intent.

## Degrade, don't fail

Catalog fetches have three tiers: annotated catalog → plain `/v1/models` →
curated `fallback_models`. Keep it that way. Any new fetch path must fall
through rather than raise; an empty picker is worse than a stale one.

## Do not write agent-config filenames into tracked files

Hermes security-scans a Git source before installing it (`tools/skills_guard.py`).
One of its **critical** rules, `agent_config_mod`, matches the bare filenames of
the well-known agent-instruction files — this repository's own top-level one,
its Claude-flavoured sibling, and the two editor rule-files (Cursor's and
Cline's dot-prefixed ones). A single critical finding makes the verdict
`dangerous`, and a dangerous verdict on a community source is a hard block that
`--force` cannot override. So one such string anywhere in a tracked file makes

```
hermes plugins install AIhubmix/hermes-provider-aihubmix
```

fail for every user. The scanner reads file *contents*, not paths, so this file
being named what it is on disk is fine — writing that name *inside* any tracked
file is not.

Refer to the upstream policy by its text ("No new third-party-product plugins
in-tree") rather than by filename. `scripts/check_sensitive.py` enforces this
and runs in CI; it assembles the patterns from fragments and skips itself, which
is why it can name what it looks for and this file cannot.

Medium findings are noise by comparison — `_determine_verdict` treats
medium/low as informational and non-blocking. Expect roughly three dozen of
them from `self.profile` in the tests, which the shell-startup-file pattern
`\.(bashrc|zshrc|profile|...)` matches on the attribute name. Leave them.

## Before opening a PR

```bash
python3 scripts/check_sensitive.py
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Run `AIHUBMIX_API_KEY=... python3 scripts/update_catalog.py` when touching
`fallback_models` or `default_aux_model`.
