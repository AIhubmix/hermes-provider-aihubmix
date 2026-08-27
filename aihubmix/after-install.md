# AIHubMix provider installed — one step remains

Hermes discovers model providers only under
`~/.hermes/plugins/model-providers/`, and `hermes plugins install` places every
plugin one level up. Tracked at NousResearch/hermes-agent#76372.

To finish:

    mkdir -p ~/.hermes/plugins/model-providers
    mv ~/.hermes/plugins/aihubmix ~/.hermes/plugins/model-providers/aihubmix

Then restart the gateway: `hermes gateway restart`.

`pip install` is the other supported path and needs none of this; see the
README.

Answer N to the next prompt. Enabling has no effect on a directory-installed
provider.
