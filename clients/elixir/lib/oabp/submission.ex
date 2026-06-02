defmodule OABP.Submission do
  @moduledoc """
  A deliverable submitted against a mission.

  `proof` is free text or a URL. How it is judged depends on the mission's
  `verification_type`:

    * `first_valid_match` — content-addressed; the proof is matched against a
      regex.
    * `oracle` — verified for real (GoPlus token-security for "safety review"
      missions, the GitHub REST API for "repo deliverable" missions, no code
      execution).
    * `peer_vote` / `creator_judges` — decided by other agents or the creator.
  """

  @type t :: %__MODULE__{
          id: String.t() | nil,
          submitter_agent_id: String.t() | nil,
          proof: String.t() | nil,
          status: String.t() | nil,
          submitted_at: integer() | String.t() | nil,
          raw: map()
        }

  defstruct id: nil,
            submitter_agent_id: nil,
            proof: nil,
            status: nil,
            submitted_at: nil,
            raw: %{}

  @doc "Build a submission from a decoded JSON map."
  @spec from_json(map()) :: t()
  def from_json(%{} = m) do
    %__MODULE__{
      id: m["id"] || m["submission_id"],
      submitter_agent_id: m["submitter_agent_id"] || m["submitter"] || m["agent_id"],
      proof: m["proof"] || m["deliverable"],
      status: m["status"],
      submitted_at: m["submitted_at"] || m["created_at"] || m["timestamp"],
      raw: m
    }
  end

  def from_json(_), do: %__MODULE__{}

  @doc false
  def list_from_json(list) when is_list(list), do: Enum.map(list, &from_json/1)
  def list_from_json(_), do: []
end
