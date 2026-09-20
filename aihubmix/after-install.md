# AIHubMix provider installed

Nothing further is required on current Hermes builds. Set a key and run it:

    export AIHUBMIX_API_KEY="AIHUBMIX_XXX"
    hermes --provider aihubmix --model gpt-5.6-sol

Get a key at <https://aihubmix.com/token>. `hermes doctor` probes the variable
against the live catalog.

## If the provider does not appear

Builds predating 2026-09-02 discover model providers only under
`~/.hermes/plugins/model-providers/`, while `hermes plugins install` clones one
level up, so the plugin lands on disk and never registers. The discovery-side
fix for that mismatch (NousResearch/hermes-agent#76372, landed via #101456)
also picks up plugins already installed the broken way.

Upgrading Hermes is the real fix. On a build that predates it, move the
directory once:

    mkdir -p ~/.hermes/plugins/model-providers
    mv ~/.hermes/plugins/aihubmix ~/.hermes/plugins/model-providers/aihubmix
    hermes gateway restart
