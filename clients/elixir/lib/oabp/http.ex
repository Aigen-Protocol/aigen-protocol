defmodule OABP.HTTP do
  @moduledoc """
  HTTP transport contract and request plumbing for the OABP SDK.

  ### Behaviour

  An adapter implements one callback:

      @callback request(method, url, headers, body, opts) ::
                  {:ok, status, resp_headers, resp_body} | {:error, term()}

  Two adapters ship with the library:

    * `OABP.HTTP.Finch` — production default, built on `Finch` (the spec
      transport, the engine under `Req`).
    * `OABP.HTTP.Httpc` — zero-dependency fallback built on OTP `:httpc`,
      used in the test suite and whenever Finch is unavailable.

  This module also holds the JSON request/response helpers shared by every
  `OABP` call, so adapters stay tiny and only move bytes.
  """

  alias OABP.{Client, Error}

  @type method :: :get | :post | :put | :delete | :patch
  @type headers :: [{String.t(), String.t()}]

  @callback request(
              method(),
              url :: String.t(),
              headers(),
              body :: binary() | nil,
              opts :: keyword()
            ) ::
              {:ok, status :: non_neg_integer(), headers(), body :: binary()}
              | {:error, term()}

  @user_agent "oabp-elixir/0.1.0"

  @doc """
  Issue a request and return a decoded JSON map/list on a 2xx response.

  Returns `{:ok, decoded}` or `{:error, %OABP.Error{}}`. Non-2xx becomes an
  `:http` error (with the raw body parsed as JSON when possible); a dropped
  connection becomes a `:transport` error; malformed JSON becomes a `:decode`
  error.
  """
  @spec request_json(Client.t(), method(), String.t(), keyword()) ::
          {:ok, term()} | {:error, Error.t()}
  def request_json(%Client{} = client, method, path, opts \\ []) do
    url = client.base_url <> path
    {body, headers} = encode_body(Keyword.get(opts, :json))
    headers = base_headers(client) ++ headers

    case client.adapter.request(method, url, headers, body, timeout: client.timeout) do
      {:ok, status, _resp_headers, resp_body} when status in 200..299 ->
        decode_json(resp_body)

      {:ok, status, _resp_headers, resp_body} ->
        {:error, Error.http(status, decode_json_loose(resp_body))}

      {:error, reason} ->
        {:error, Error.transport(reason)}
    end
  end

  @doc false
  def base_headers(%Client{headers: extra}) do
    [
      {"accept", "application/json"},
      {"user-agent", @user_agent}
    ] ++ extra
  end

  defp encode_body(nil), do: {nil, []}

  defp encode_body(map) do
    {Jason.encode!(map), [{"content-type", "application/json"}]}
  end

  defp decode_json(""), do: {:ok, %{}}

  defp decode_json(body) when is_binary(body) do
    case Jason.decode(body) do
      {:ok, decoded} -> {:ok, decoded}
      {:error, _} -> {:error, Error.decode("response body was not valid JSON", body)}
    end
  end

  # Best-effort: used for error bodies, where we want structured detail if the
  # server sent JSON but must not blow up if it sent plain text/HTML.
  defp decode_json_loose(body) when is_binary(body) do
    case Jason.decode(body) do
      {:ok, decoded} -> decoded
      {:error, _} -> body
    end
  end

  defp decode_json_loose(other), do: other
end
