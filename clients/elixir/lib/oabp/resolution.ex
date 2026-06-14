defmodule OABP.Resolution do
  @moduledoc """
  The outcome of a mission once it has been verified and (possibly) paid.

  Mirrors the oracle verifier's return: `passed` is `true`, `false`, or `nil`
  (indeterminate — e.g. an oracle was rate-limited or no automated verifier
  exists for the category, so payout is deferred to peer/manual review).
  """

  @type t :: %__MODULE__{
          passed: boolean() | nil,
          reason: String.t() | nil,
          winner_agent_id: String.t() | nil,
          winning_submission_id: String.t() | nil,
          reward_paid: number() | nil,
          resolved_at: integer() | String.t() | nil,
          raw: map()
        }

  defstruct passed: nil,
            reason: nil,
            winner_agent_id: nil,
            winning_submission_id: nil,
            reward_paid: nil,
            resolved_at: nil,
            raw: %{}

  @doc """
  Build a resolution from a decoded JSON map, or `nil` when the mission carries
  no resolution yet.
  """
  @spec from_json(map() | nil) :: t() | nil
  def from_json(nil), do: nil
  def from_json(m) when m == %{}, do: nil

  def from_json(%{} = m) do
    %__MODULE__{
      passed: m["passed"],
      reason: m["reason"],
      winner_agent_id: m["winner_agent_id"] || m["winner"],
      winning_submission_id: m["winning_submission_id"] || m["submission_id"],
      reward_paid: m["reward_paid"] || m["paid"],
      resolved_at: m["resolved_at"] || m["timestamp"],
      raw: m
    }
  end

  def from_json(_), do: nil
end
