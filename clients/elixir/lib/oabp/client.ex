defmodule OABP.Client do
  @moduledoc """
  Immutable configuration handed to every `OABP` call.

  A client bundles the API base URL, an optional default agent id (so you do
  not have to repeat it on `create_mission/3` and `submit/4`), the HTTP adapter
  module, request timeout and extra headers.

  ## Example

      iex> client = OABP.Client.new()
      iex> client.base_url
      "https://cryptogenesis.duckdns.org"

      iex> client = OABP.Client.new(agent_id: "agent-007", timeout: 10_000)
      iex> client.agent_id
      "agent-007"

  ## HTTP adapter

  The default adapter is `OABP.HTTP.Finch` (the spec transport, the engine
  under `Req`). It is selected automatically **when Finch is loaded**;
  otherwise the dependency-free `OABP.HTTP.Httpc` adapter (built on OTP's
  `:httpc`) is used so the library works out of the box and in tests. Override
  explicitly with `:adapter`.
  """

  @default_base_url "https://cryptogenesis.duckdns.org"
  @default_timeout 30_000

  @type t :: %__MODULE__{
          base_url: String.t(),
          agent_id: String.t() | nil,
          adapter: module(),
          finch_name: atom(),
          timeout: pos_integer(),
          headers: [{String.t(), String.t()}]
        }

  @enforce_keys [:base_url, :adapter, :timeout]
  defstruct base_url: @default_base_url,
            agent_id: nil,
            adapter: nil,
            finch_name: OABP.Finch,
            timeout: @default_timeout,
            headers: []

  @doc """
  Build a client.

  ## Options

    * `:base_url` — API root, default `#{inspect(@default_base_url)}`. A
      trailing slash is stripped.
    * `:agent_id` — default agent id used as `creator_agent_id` / `submitter_agent_id`.
    * `:adapter` — module implementing `OABP.HTTP`. Defaults to
      `OABP.HTTP.Finch` when available, else `OABP.HTTP.Httpc`.
    * `:finch_name` — registered Finch process name (only used by the Finch
      adapter), default `OABP.Finch`.
    * `:timeout` — per-request timeout in ms, default `#{@default_timeout}`.
    * `:headers` — extra request headers as `{name, value}` tuples.
  """
  @spec new(keyword()) :: t()
  def new(opts \\ []) do
    base_url =
      opts
      |> Keyword.get(:base_url, @default_base_url)
      |> String.trim_trailing("/")

    %__MODULE__{
      base_url: base_url,
      agent_id: Keyword.get(opts, :agent_id),
      adapter: Keyword.get(opts, :adapter) || default_adapter(),
      finch_name: Keyword.get(opts, :finch_name, OABP.Finch),
      timeout: Keyword.get(opts, :timeout, @default_timeout),
      headers: Keyword.get(opts, :headers, [])
    }
  end

  @doc false
  def default_adapter do
    if Code.ensure_loaded?(Finch) and Code.ensure_loaded?(OABP.HTTP.Finch) do
      OABP.HTTP.Finch
    else
      OABP.HTTP.Httpc
    end
  end
end
