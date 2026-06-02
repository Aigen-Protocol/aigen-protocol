import Config

# The OABP SDK is configured per-client via `OABP.Client.new/1`, so there is no
# global application config to set here. This file exists so the project builds
# uniformly under any `MIX_ENV` and so host applications can drop in their own
# `config/runtime.exs` (e.g. to start a Finch pool) without surprises.
#
# Example host-app supervision (when using the default Finch transport):
#
#     # lib/my_app/application.ex
#     children = [
#       {Finch, name: OABP.Finch}
#     ]
#
#     # build a client wherever you call the API:
#     client = OABP.Client.new(agent_id: System.fetch_env!("AIGEN_AGENT_ID"))
