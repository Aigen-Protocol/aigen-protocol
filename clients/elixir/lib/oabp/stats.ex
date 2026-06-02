defmodule OABP.Stats do
  @moduledoc """
  Ecosystem counters from `GET /api/stats`: how many missions are `resolved`
  vs `open`, and the lifetime AIGEN paid out across all resolutions.
  """

  @type t :: %__MODULE__{
          resolved: non_neg_integer(),
          open: non_neg_integer(),
          lifetime_reward_aigen_paid: number(),
          raw: map()
        }

  defstruct resolved: 0,
            open: 0,
            lifetime_reward_aigen_paid: 0,
            raw: %{}

  @doc "Build stats from a decoded JSON map."
  @spec from_json(map()) :: t()
  def from_json(%{} = m) do
    %__MODULE__{
      resolved: integer(m["resolved"]),
      open: integer(m["open"]),
      lifetime_reward_aigen_paid:
        number(m["lifetime_reward_aigen_paid"] || m["lifetime_aigen_paid"]),
      raw: m
    }
  end

  def from_json(_), do: %__MODULE__{}

  defp integer(n) when is_integer(n), do: n
  defp integer(n) when is_float(n), do: trunc(n)
  defp integer(_), do: 0

  defp number(n) when is_number(n), do: n
  defp number(_), do: 0
end
