# Changelog

## Unreleased

- Manifest `name` is now `aihubmix`, matching the pip entry point, the
  community index entry, and the provider id the registry exposes. Directory
  installs previously landed in `plugins/aihubmix-provider/` while every other
  identifier for this plugin was `aihubmix`.

## 0.1.0

- Initial release: registers AIHubMix as the `aihubmix` model provider for
  Hermes Agent over the OpenAI-compatible Chat Completions endpoint.
- `fetch_models` prefers the capability-annotated catalog
  (`/api/v1/models?types=llm`) and keeps only tool-capable models, falling
  back to `/v1/models` when that catalog is unreachable or filters to zero.
- Curated `fallback_models` for offline starts, staleness-checked by
  `scripts/update_catalog.py`.
