defmodule OABP.HTTP.Httpc do
  @moduledoc """
  Dependency-free `OABP.HTTP` adapter built on OTP's bundled `:httpc` client
  (`:inets`).

  Requires no external packages and no native compilation, which makes it the
  reliable fallback when `Finch` is not present and the transport used by the
  test suite (against a local `Bypass` server). For production workloads with
  connection pooling and HTTP/2, prefer `OABP.HTTP.Finch`.
  """

  @behaviour OABP.HTTP

  @impl true
  def request(method, url, headers, body, opts) do
    timeout = Keyword.get(opts, :timeout, 30_000)
    _ = ensure_started()

    url_charlist = String.to_charlist(url)

    header_list =
      Enum.map(headers, fn {k, v} -> {String.to_charlist(k), String.to_charlist(v)} end)

    http_opts = [timeout: timeout, connect_timeout: timeout, autoredirect: false]
    # Return the body as a binary, never auto-decode, never stream.
    req_opts = [body_format: :binary]

    request_tuple = build_request(url_charlist, header_list, body)

    case :httpc.request(method, request_tuple, http_opts, req_opts) do
      {:ok, {{_http_vsn, status, _reason}, resp_headers, resp_body}} ->
        {:ok, status, normalize_headers(resp_headers), to_binary(resp_body)}

      {:error, reason} ->
        {:error, reason}
    end
  end

  # GET/DELETE: no body, 2-tuple request.
  defp build_request(url, headers, body) when body in [nil, ""] do
    {url, headers}
  end

  # POST/PUT/PATCH: 4-tuple request carrying content-type + body.
  defp build_request(url, headers, body) do
    {content_type, headers} = pop_content_type(headers)
    {url, headers, content_type, body}
  end

  defp pop_content_type(headers) do
    case Enum.split_with(headers, fn {k, _v} -> :string.to_lower(k) == ~c"content-type" end) do
      {[{_k, ct} | _], rest} -> {ct, rest}
      {[], rest} -> {~c"application/json", rest}
    end
  end

  defp normalize_headers(headers) do
    Enum.map(headers, fn {k, v} -> {to_binary(k) |> String.downcase(), to_binary(v)} end)
  end

  defp to_binary(value) when is_list(value), do: List.to_string(value)
  defp to_binary(value) when is_binary(value), do: value

  defp ensure_started do
    {:ok, _} = Application.ensure_all_started(:inets)
    {:ok, _} = Application.ensure_all_started(:ssl)
    :ok
  end
end
