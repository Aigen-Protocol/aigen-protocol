defmodule OABP.Error do
  @moduledoc """
  Structured error returned in the `{:error, %OABP.Error{}}` tuple by every
  `OABP` function.

  The `:kind` field lets callers pattern-match on the failure category without
  parsing strings:

    * `:http` — the API answered with a non-2xx status. `:status` and `:body`
      are populated.
    * `:transport` — the request never completed (connection refused, DNS,
      timeout, TLS). `:reason` holds the underlying term.
    * `:decode` — the response was not the JSON shape we expected.
    * `:rpc` — an A2A JSON-RPC call returned an `error` object. `:status`
      carries the JSON-RPC error code and `:body` the full error map.
    * `:invalid` — the arguments handed to the SDK were not usable.
  """

  @type kind :: :http | :transport | :decode | :rpc | :invalid

  @type t :: %__MODULE__{
          kind: kind(),
          message: String.t(),
          status: integer() | nil,
          reason: term(),
          body: term()
        }

  defexception [:kind, :message, :status, :reason, :body]

  @impl true
  def message(%__MODULE__{kind: kind, message: msg, status: nil}),
    do: "OABP #{kind} error: #{msg}"

  def message(%__MODULE__{kind: kind, message: msg, status: status}),
    do: "OABP #{kind} error (#{status}): #{msg}"

  @doc false
  def http(status, body),
    do: %__MODULE__{kind: :http, message: http_phrase(status), status: status, body: body}

  @doc false
  def transport(reason),
    do: %__MODULE__{
      kind: :transport,
      message: "request failed: #{inspect(reason)}",
      reason: reason
    }

  @doc false
  def decode(message, body \\ nil),
    do: %__MODULE__{kind: :decode, message: message, body: body}

  @doc false
  def rpc(code, error_obj) do
    msg = if is_map(error_obj), do: Map.get(error_obj, "message", "rpc error"), else: "rpc error"
    %__MODULE__{kind: :rpc, message: msg, status: code, body: error_obj}
  end

  @doc false
  def invalid(message), do: %__MODULE__{kind: :invalid, message: message}

  defp http_phrase(400), do: "bad request"
  defp http_phrase(401), do: "unauthorized"
  defp http_phrase(403), do: "forbidden"
  defp http_phrase(404), do: "not found"
  defp http_phrase(409), do: "conflict"
  defp http_phrase(422), do: "unprocessable entity"
  defp http_phrase(429), do: "rate limited"
  defp http_phrase(code) when code >= 500, do: "server error"
  defp http_phrase(_), do: "unexpected status"
end
