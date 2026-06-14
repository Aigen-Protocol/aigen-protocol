"""Entry point for the OABP / AIGEN Dify plugin.

Dify's plugin runner imports this module (``entrypoint: main`` in
``manifest.yaml``) and runs ``plugin.run()``. The :class:`~dify_plugin.Plugin`
object discovers the tool provider declared in ``provider/oabp.yaml`` and the
five tools under ``tools/`` automatically from their YAML manifests, so there is
nothing else to register here.
"""

from dify_plugin import DifyPluginEnv, Plugin

# A slightly generous timeout: the OABP marketplace runs oracle verification
# (GoPlus / GitHub REST) synchronously on submit, which can take a few seconds.
plugin = Plugin(DifyPluginEnv(MAX_REQUEST_TIMEOUT=120))


if __name__ == "__main__":
    plugin.run()
