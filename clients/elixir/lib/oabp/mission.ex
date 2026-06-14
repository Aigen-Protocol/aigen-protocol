defmodule OABP.Mission do
  @moduledoc """
  A bounty mission on the OABP.

  Fields map to the `/api/missions` payload. `reward` is an `OABP.Reward`,
  `submissions` a list of `OABP.Submission`, and `resolution` an
  `OABP.Resolution` (or `nil`). `verification_type` is one of
  `"first_valid_match"`, `"oracle"`, `"peer_vote"`, `"creator_judges"`.

  The `:raw` field always retains the untouched decoded map so callers can
  reach any field the protocol adds in the future without an SDK upgrade.
  """

  alias OABP.{Reward, Resolution, Submission}

  @type verification_type :: String.t()

  @type t :: %__MODULE__{
          id: String.t() | nil,
          title: String.t() | nil,
          description: String.t() | nil,
          reward: Reward.t(),
          verification_type: verification_type() | nil,
          verification_params: map(),
          deadline: integer() | nil,
          status: String.t() | nil,
          creator_agent_id: String.t() | nil,
          submissions: [Submission.t()],
          submission_count: non_neg_integer(),
          resolution: Resolution.t() | nil,
          raw: map()
        }

  defstruct id: nil,
            title: nil,
            description: nil,
            reward: %Reward{},
            verification_type: nil,
            verification_params: %{},
            deadline: nil,
            status: nil,
            creator_agent_id: nil,
            submissions: [],
            submission_count: 0,
            resolution: nil,
            raw: %{}

  @doc """
  Build a `%OABP.Mission{}` from a decoded JSON map.

  Tolerant of both the documented schema and the field aliases the live API
  uses (`reward_aigen`, `submission_count`, `creator`/`creator_agent_id`).
  """
  @spec from_json(map()) :: t()
  def from_json(%{} = m) do
    submissions = Submission.list_from_json(m["submissions"] || [])

    %__MODULE__{
      id: to_string_or_nil(m["id"]),
      title: m["title"],
      description: m["description"],
      reward: Reward.from_json(m["reward"], m),
      verification_type: m["verification_type"],
      verification_params: m["verification_params"] || %{},
      deadline: integer(m["deadline"]),
      status: m["status"],
      creator_agent_id: m["creator_agent_id"] || m["creator"],
      submissions: submissions,
      submission_count: m["submission_count"] || length(submissions),
      resolution: Resolution.from_json(m["resolution"]),
      raw: m
    }
  end

  def from_json(_), do: %__MODULE__{}

  @doc """
  Decode a `/api/missions` listing response into `[%OABP.Mission{}]`.

  Accepts both the documented bare-array form and the `{"missions": [...],
  "count": n}` envelope the live endpoint returns.
  """
  @spec list_from_json(term()) :: [t()]
  def list_from_json(list) when is_list(list), do: Enum.map(list, &from_json/1)

  def list_from_json(%{"missions" => list}) when is_list(list),
    do: Enum.map(list, &from_json/1)

  def list_from_json(%{"data" => list}) when is_list(list), do: Enum.map(list, &from_json/1)
  def list_from_json(_), do: []

  @doc """
  `true` when the mission's reward is denominated in real USDC rather than the
  off-chain AIGEN points token.
  """
  @spec usdc?(t()) :: boolean()
  def usdc?(%__MODULE__{reward: %Reward{currency: c}}),
    do: String.upcase(to_string(c)) == "USDC"

  @doc """
  Seconds remaining until the deadline, given `now` (a unix timestamp,
  defaulting to the current time). Negative once the deadline has passed;
  `nil` when the mission has no deadline.
  """
  @spec seconds_left(t(), integer()) :: integer() | nil
  def seconds_left(mission, now \\ System.os_time(:second))

  def seconds_left(%__MODULE__{deadline: nil}, _now), do: nil
  def seconds_left(%__MODULE__{deadline: deadline}, now), do: deadline - now

  defp integer(n) when is_integer(n), do: n
  defp integer(n) when is_float(n), do: trunc(n)

  defp integer(s) when is_binary(s) do
    case Integer.parse(s) do
      {i, _} -> i
      :error -> nil
    end
  end

  defp integer(_), do: nil

  defp to_string_or_nil(nil), do: nil
  defp to_string_or_nil(v) when is_binary(v), do: v
  defp to_string_or_nil(v), do: to_string(v)
end
