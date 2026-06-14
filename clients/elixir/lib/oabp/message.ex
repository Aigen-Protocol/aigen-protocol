defmodule OABP.Message do
  @moduledoc """
  An A2A (Agent2Agent) message — the result of an `OABP.a2a_send/3` call.

  Mirrors the A2A `Message` object the protocol returns: a `role` (`"agent"`),
  a `message_id`, an optional `context_id`, and an ordered list of
  `OABP.Part`. `text/1` joins every text part for quick display.
  """

  alias OABP.Part

  @type t :: %__MODULE__{
          kind: String.t(),
          role: String.t() | nil,
          message_id: String.t() | nil,
          context_id: String.t() | nil,
          task_id: String.t() | nil,
          parts: [Part.t()],
          raw: map()
        }

  defstruct kind: "message",
            role: nil,
            message_id: nil,
            context_id: nil,
            task_id: nil,
            parts: [],
            raw: %{}

  @doc "Build a message from a decoded A2A result map."
  @spec from_json(map()) :: t()
  def from_json(%{} = m) do
    parts =
      case m["parts"] do
        list when is_list(list) -> Enum.map(list, &Part.from_json/1)
        _ -> []
      end

    %__MODULE__{
      kind: m["kind"] || "message",
      role: m["role"],
      message_id: m["messageId"] || m["message_id"],
      context_id: m["contextId"] || m["context_id"],
      task_id: m["taskId"] || m["task_id"],
      parts: parts,
      raw: m
    }
  end

  def from_json(_), do: %__MODULE__{}

  @doc """
  All text parts joined with newlines — the human-readable view of the
  message.
  """
  @spec text(t()) :: String.t()
  def text(%__MODULE__{parts: parts}) do
    parts
    |> Enum.filter(&(&1.kind == "text" and is_binary(&1.text)))
    |> Enum.map_join("\n", & &1.text)
  end

  @doc """
  The `data` of the first `"data"` part, or `nil` — e.g. the structured
  mission feed an agent attaches to a textual reply.
  """
  @spec data(t()) :: term() | nil
  def data(%__MODULE__{parts: parts}) do
    case Enum.find(parts, &(&1.kind == "data")) do
      %Part{data: data} -> data
      _ -> nil
    end
  end
end
