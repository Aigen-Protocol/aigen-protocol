defmodule OABP.Part do
  @moduledoc """
  One content part of an A2A `OABP.Message`.

  A2A parts are tagged by `kind`:

    * `"text"` — human-readable text in `:text`.
    * `"data"` — a structured JSON value in `:data` (e.g. the live mission
      feed embedded alongside a textual summary).
    * `"file"` — file content/reference in `:data`.
  """

  @type t :: %__MODULE__{
          kind: String.t(),
          text: String.t() | nil,
          data: term()
        }

  defstruct kind: "text", text: nil, data: nil

  @doc "Build a part from a decoded A2A part map."
  @spec from_json(map()) :: t()
  def from_json(%{} = p) do
    %__MODULE__{
      kind: p["kind"] || "text",
      text: p["text"],
      data: p["data"]
    }
  end

  def from_json(_), do: %__MODULE__{}

  @doc "A text part, for building an outbound message."
  @spec text(String.t()) :: t()
  def text(str) when is_binary(str), do: %__MODULE__{kind: "text", text: str}

  @doc "A data part, for building an outbound message."
  @spec data(term()) :: t()
  def data(value), do: %__MODULE__{kind: "data", data: value}

  @doc false
  def to_wire(%__MODULE__{kind: "text", text: text}), do: %{"kind" => "text", "text" => text}
  def to_wire(%__MODULE__{kind: "data", data: data}), do: %{"kind" => "data", "data" => data}

  def to_wire(%__MODULE__{kind: kind, text: text, data: data}),
    do: %{"kind" => kind, "text" => text, "data" => data}
end
