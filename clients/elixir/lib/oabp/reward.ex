defmodule OABP.Reward do
  @moduledoc """
  A mission reward: an `amount` denominated in a `currency` (`"AIGEN"` or
  `"USDC"`).

  AIGEN is the protocol's uncapped, off-chain reputation/points token; USDC
  rewards represent real value. A 0.5% protocol fee applies on resolution.
  """

  @type currency :: String.t()

  @type t :: %__MODULE__{
          amount: number(),
          currency: currency()
        }

  defstruct amount: 0, currency: "AIGEN"

  @doc """
  Build a reward from a decoded JSON value.

  Accepts the nested object form (`%{"amount" => 100, "currency" => "AIGEN"}`)
  as documented, and degrades gracefully to the flat `reward_aigen` field the
  live `/api/missions` feed sometimes uses.
  """
  @spec from_json(map() | number() | nil, map()) :: t()
  def from_json(reward, parent \\ %{})

  def from_json(%{} = reward, _parent) do
    %__MODULE__{
      amount: number(reward["amount"]),
      currency: reward["currency"] || "AIGEN"
    }
  end

  def from_json(amount, _parent) when is_number(amount) do
    %__MODULE__{amount: amount, currency: "AIGEN"}
  end

  def from_json(_other, parent) when is_map(parent) do
    %__MODULE__{
      amount: number(parent["reward_aigen"] || parent["reward_amount"]),
      currency: parent["reward_currency"] || "AIGEN"
    }
  end

  def from_json(_other, _parent), do: %__MODULE__{}

  defp number(n) when is_number(n), do: n

  defp number(s) when is_binary(s) do
    case Float.parse(s) do
      {f, _} -> f
      :error -> 0
    end
  end

  defp number(_), do: 0
end
