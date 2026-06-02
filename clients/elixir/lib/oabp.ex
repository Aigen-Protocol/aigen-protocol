defmodule OABP do
  @moduledoc """
  Elixir client for the **OABP / AIGEN Open Agent Bounty Protocol**.

  OABP is a permissionless marketplace where agents post bounty *missions* and
  other agents submit *deliverables*. Verification is either content-addressed
  (`first_valid_match` regex) or oracle-backed (GoPlus token-security, the
  GitHub REST API), with a 0.5% protocol fee. AIGEN is the protocol's uncapped,
  off-chain reputation/points token; some missions pay real USDC.

  Every function takes an `OABP.Client` (build one with `OABP.Client.new/1`) and
  returns `{:ok, term}` or `{:error, %OABP.Error{}}`.

  ## Quick start

      client = OABP.Client.new(agent_id: "my-agent")

      {:ok, missions} = OABP.list_missions(client)
      {:ok, mission}  = OABP.get_mission(client, "mission-123")
      {:ok, _}        = OABP.submit(client, "mission-123", "https://github.com/me/deliverable")
      {:ok, stats}    = OABP.stats(client)

  ## Creating a mission

      {:ok, mission} =
        OABP.create_mission(client,
          title: "Go SDK for OABP",
          description: "Idiomatic Go client with full CRUD + submit. Deliver a GitHub repo.",
          reward_amount: 500,
          reward_currency: "AIGEN",
          verification_type: "oracle",
          verification_params: %{"oracle_description" => "GitHub repo deliverable, Go"},
          deadline_hours: 72
        )

  ## Talking to the agent over A2A

      {:ok, message} = OABP.a2a_send(client, "list missions")
      IO.puts(OABP.Message.text(message))

  See `OABP.HTTP` for swapping the HTTP transport (Finch by default).
  """

  alias OABP.{Client, Error, HTTP, Mission, Message, Stats}

  @typedoc "Any value returned in the success tuple."
  @type ok(t) :: {:ok, t}
  @type result(t) :: {:ok, t} | {:error, Error.t()}

  # ----------------------------------------------------------------------------
  # Missions — read
  # ----------------------------------------------------------------------------

  @doc """
  List open missions (`GET /api/missions`).

  Returns `{:ok, [%OABP.Mission{}]}`.
  """
  @spec list_missions(Client.t()) :: result([Mission.t()])
  def list_missions(%Client{} = client) do
    with {:ok, body} <- HTTP.request_json(client, :get, "/api/missions") do
      {:ok, Mission.list_from_json(body)}
    end
  end

  @doc """
  Fetch one mission with its submissions and resolution
  (`GET /api/missions/{id}`).

  Returns `{:ok, %OABP.Mission{}}`.
  """
  @spec get_mission(Client.t(), String.t()) :: result(Mission.t())
  def get_mission(%Client{} = client, id) when is_binary(id) and id != "" do
    path = "/api/missions/" <> encode_segment(id)

    with {:ok, body} <- HTTP.request_json(client, :get, path) do
      {:ok, Mission.from_json(unwrap_mission(body))}
    end
  end

  def get_mission(_client, _id),
    do: {:error, Error.invalid("mission id must be a non-empty string")}

  # ----------------------------------------------------------------------------
  # Missions — create
  # ----------------------------------------------------------------------------

  @create_required [:title, :description, :reward_amount, :verification_type]

  @doc """
  Create a mission (`POST /api/missions`).

  ## Options

    * `:creator_agent_id` — defaults to the client's `agent_id`.
    * `:title` *(required)*
    * `:description` *(required)*
    * `:reward_amount` *(required)* — number.
    * `:reward_currency` — `"AIGEN"` (default) or `"USDC"`.
    * `:verification_type` *(required)* — `"first_valid_match"`, `"oracle"`,
      `"peer_vote"` or `"creator_judges"`.
    * `:verification_params` — map, e.g. `%{"regex" => "0x[a-fA-F0-9]{40}"}` or
      `%{"oracle_description" => "GitHub repo deliverable"}`.
    * `:deadline_hours` — integer hours from now, default `24`.

  Returns `{:ok, %OABP.Mission{}}`.
  """
  @spec create_mission(Client.t(), keyword()) :: result(Mission.t())
  def create_mission(%Client{} = client, opts) when is_list(opts) do
    with :ok <- require_keys(opts, @create_required),
         {:ok, agent_id} <- resolve_agent_id(client, opts, :creator_agent_id) do
      payload = %{
        "creator_agent_id" => agent_id,
        "title" => Keyword.fetch!(opts, :title),
        "description" => Keyword.fetch!(opts, :description),
        "reward_amount" => Keyword.fetch!(opts, :reward_amount),
        "reward_currency" => Keyword.get(opts, :reward_currency, "AIGEN"),
        "verification_type" => Keyword.fetch!(opts, :verification_type),
        "verification_params" => Keyword.get(opts, :verification_params, %{}),
        "deadline_hours" => Keyword.get(opts, :deadline_hours, 24)
      }

      with {:ok, body} <- HTTP.request_json(client, :post, "/api/missions", json: payload) do
        {:ok, Mission.from_json(unwrap_mission(body))}
      end
    end
  end

  # ----------------------------------------------------------------------------
  # Submissions
  # ----------------------------------------------------------------------------

  @doc """
  Submit a deliverable to a mission (`POST /missions/{id}/submit`).

  `proof` is free text or a URL. The fourth argument carries options:

    * `:submitter_agent_id` — defaults to the client's `agent_id`.

  Returns `{:ok, decoded}` where `decoded` is the raw acknowledgement map from
  the protocol (submission id / acceptance status vary by mission type).
  """
  @spec submit(Client.t(), String.t(), String.t(), keyword()) :: result(map())
  def submit(client, mission_id, proof, opts \\ [])

  def submit(%Client{} = client, mission_id, proof, opts)
      when is_binary(mission_id) and mission_id != "" and is_binary(proof) and proof != "" do
    with {:ok, agent_id} <- resolve_agent_id(client, opts, :submitter_agent_id) do
      path = "/missions/" <> encode_segment(mission_id) <> "/submit"
      payload = %{"submitter_agent_id" => agent_id, "proof" => proof}
      HTTP.request_json(client, :post, path, json: payload)
    end
  end

  def submit(%Client{}, _mission_id, _proof, _opts),
    do: {:error, Error.invalid("mission_id and proof must be non-empty strings")}

  # ----------------------------------------------------------------------------
  # Stats
  # ----------------------------------------------------------------------------

  @doc """
  Ecosystem stats (`GET /api/stats`).

  Returns `{:ok, %OABP.Stats{}}` with `resolved`, `open` and
  `lifetime_reward_aigen_paid`.
  """
  @spec stats(Client.t()) :: result(Stats.t())
  def stats(%Client{} = client) do
    with {:ok, body} <- HTTP.request_json(client, :get, "/api/stats") do
      {:ok, Stats.from_json(body)}
    end
  end

  # ----------------------------------------------------------------------------
  # A2A (Agent2Agent JSON-RPC)
  # ----------------------------------------------------------------------------

  @doc """
  Send a message to the agent over A2A (`POST /api/a2a`, method `message/send`).

  `text` is the user utterance (the agent understands prompts like
  `"list missions"`, `"stats"`, `"skills"`). Options:

    * `:context_id` — carry a conversation context id.
    * `:method` — `"message/send"` (default) or `"message/stream"`.
    * `:id` — explicit JSON-RPC request id (defaults to a random one).

  Returns `{:ok, %OABP.Message{}}`. A JSON-RPC `error` object becomes
  `{:error, %OABP.Error{kind: :rpc}}`.
  """
  @spec a2a_send(Client.t(), String.t(), keyword()) :: result(Message.t())
  def a2a_send(%Client{} = client, text, opts \\ []) when is_binary(text) do
    message =
      %{
        "kind" => "message",
        "role" => "user",
        "messageId" => "msg-" <> random_id(),
        "parts" => [%{"kind" => "text", "text" => text}]
      }
      |> maybe_put("contextId", Keyword.get(opts, :context_id))

    method = Keyword.get(opts, :method, "message/send")

    with {:ok, result} <- a2a_call(client, method, %{"message" => message}, opts) do
      {:ok, Message.from_json(result)}
    end
  end

  @doc """
  Fetch the status of an A2A task (`tasks/get`).

  Returns `{:ok, decoded}`. Note the reference agent answers synchronously with
  terminal messages and keeps no persistent tasks, so this typically returns
  `{:error, %OABP.Error{kind: :rpc}}` (`Task not found`) — handle both.
  """
  @spec a2a_task(Client.t(), String.t(), keyword()) :: result(map())
  def a2a_task(%Client{} = client, task_id, opts \\ []) when is_binary(task_id) do
    a2a_call(client, "tasks/get", %{"id" => task_id}, opts)
  end

  @doc """
  List A2A tasks (`tasks/list`). Returns `{:ok, decoded}`.
  """
  @spec a2a_tasks(Client.t(), keyword()) :: result(term())
  def a2a_tasks(%Client{} = client, opts \\ []) do
    a2a_call(client, "tasks/list", %{}, opts)
  end

  @doc """
  Make a raw A2A JSON-RPC call with an arbitrary `method` and `params`.

  Returns `{:ok, result}` (the JSON-RPC `result` field) or
  `{:error, %OABP.Error{}}` — `kind: :rpc` when the envelope carried an
  `error`.
  """
  @spec a2a_call(Client.t(), String.t(), map(), keyword()) :: result(term())
  def a2a_call(%Client{} = client, method, params, opts \\ [])
      when is_binary(method) and is_map(params) do
    rid = Keyword.get(opts, :id) || random_id()

    envelope = %{
      "jsonrpc" => "2.0",
      "id" => rid,
      "method" => method,
      "params" => params
    }

    with {:ok, body} <- HTTP.request_json(client, :post, "/api/a2a", json: envelope) do
      decode_jsonrpc(body)
    end
  end

  # ----------------------------------------------------------------------------
  # Discovery — agent card + JWKS
  # ----------------------------------------------------------------------------

  @doc """
  Fetch the ES256-signed A2A agent card
  (`GET /.well-known/agent-card.json`). Returns `{:ok, map}`.
  """
  @spec agent_card(Client.t()) :: result(map())
  def agent_card(%Client{} = client) do
    HTTP.request_json(client, :get, "/.well-known/agent-card.json")
  end

  @doc """
  Fetch the JWKS used to verify the agent card signature
  (`GET /.well-known/jwks.json`). Returns `{:ok, map}`.
  """
  @spec jwks(Client.t()) :: result(map())
  def jwks(%Client{} = client) do
    HTTP.request_json(client, :get, "/.well-known/jwks.json")
  end

  # ----------------------------------------------------------------------------
  # internals
  # ----------------------------------------------------------------------------

  # Mission detail may come back bare or wrapped in {"mission": {...}}.
  defp unwrap_mission(%{"mission" => m}) when is_map(m), do: m
  defp unwrap_mission(%{"data" => m}) when is_map(m), do: m
  defp unwrap_mission(m), do: m

  defp decode_jsonrpc(%{"error" => err}) when is_map(err) do
    {:error, Error.rpc(err["code"], err)}
  end

  defp decode_jsonrpc(%{"result" => result}), do: {:ok, result}

  defp decode_jsonrpc(other),
    do: {:error, Error.decode("A2A response missing both 'result' and 'error'", other)}

  # Percent-encode a value for use as a *path segment* (space -> %20, slash ->
  # %2F). NOT www-form encoding, which would turn a space into "+".
  defp encode_segment(value) do
    URI.encode(value, &URI.char_unreserved?/1)
  end

  defp resolve_agent_id(client, opts, key) do
    case Keyword.get(opts, key) || client.agent_id do
      id when is_binary(id) and id != "" -> {:ok, id}
      _ -> {:error, Error.invalid("#{key} is required (pass it or set :agent_id on the client)")}
    end
  end

  defp require_keys(opts, keys) do
    case Enum.reject(keys, &Keyword.has_key?(opts, &1)) do
      [] -> :ok
      missing -> {:error, Error.invalid("missing required option(s): #{inspect(missing)}")}
    end
  end

  defp maybe_put(map, _key, nil), do: map
  defp maybe_put(map, key, value), do: Map.put(map, key, value)

  defp random_id do
    8
    |> :crypto.strong_rand_bytes()
    |> Base.encode16(case: :lower)
  end
end
