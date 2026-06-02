if Code.ensure_loaded?(Finch) do
  defmodule OABP.HTTP.Finch do
    @moduledoc """
    Production `OABP.HTTP` adapter built on [Finch](https://hex.pm/packages/finch) —
    the HTTP transport named in the SDK spec and the engine that powers `Req`.

    Finch needs a named pool started in your supervision tree. The pool name
    defaults to `OABP.Finch`; override it with `OABP.Client.new(finch_name: ...)`.

        children = [
          {Finch, name: OABP.Finch}
        ]
        Supervisor.start_link(children, strategy: :one_for_one)

    This module is only compiled when `Finch` is loaded, so the library still
    builds (and falls back to `OABP.HTTP.Httpc`) on hosts where Finch is not a
    dependency.
    """

    @behaviour OABP.HTTP

    @default_name OABP.Finch

    @impl true
    def request(method, url, headers, body, opts) do
      timeout = Keyword.get(opts, :timeout, 30_000)
      name = Keyword.get(opts, :finch_name, @default_name)

      Finch.build(method, url, headers, body)
      |> Finch.request(name, receive_timeout: timeout)
      |> case do
        {:ok, %Finch.Response{status: status, headers: resp_headers, body: resp_body}} ->
          {:ok, status, downcase_headers(resp_headers), resp_body}

        {:error, %{__exception__: true} = exception} ->
          {:error, Exception.message(exception)}

        {:error, reason} ->
          {:error, reason}
      end
    end

    defp downcase_headers(headers) do
      Enum.map(headers, fn {k, v} -> {String.downcase(k), v} end)
    end
  end
end
