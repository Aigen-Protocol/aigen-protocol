defmodule OABP.MixProject do
  use Mix.Project

  @version "0.1.0"
  @source_url "https://github.com/aigen-protocol/oabp-elixir"

  def project do
    [
      app: :oabp,
      version: @version,
      elixir: "~> 1.12",
      elixirc_paths: elixirc_paths(Mix.env()),
      start_permanent: Mix.env() == :prod,
      deps: deps(),
      name: "OABP",
      description: description(),
      package: package(),
      source_url: @source_url,
      docs: docs(),
      test_coverage: [summary: [threshold: 0]],
      dialyzer: [plt_add_apps: [:finch, :inets, :ssl]]
    ]
  end

  def application do
    # `:inets` + `:ssl` back the dependency-free built-in HTTP adapter
    # (OABP.HTTP.Httpc). Finch, when used, starts its own supervision tree
    # under the host application — we do not start it here.
    [
      extra_applications: [:logger, :inets, :ssl]
    ]
  end

  defp elixirc_paths(:test), do: ["lib", "test/support"]
  defp elixirc_paths(_), do: ["lib"]

  defp deps do
    [
      # --- runtime ---
      {:jason, "~> 1.4"},
      # Default production HTTP transport (the engine under Req). Optional so
      # the library still compiles on a host that has not built Finch's native
      # TLS shims; the built-in :httpc adapter is always available as a fallback.
      {:finch, "~> 0.16", optional: true},

      # --- dev / test ---
      {:bypass, "~> 2.1", only: :test},
      # Pin Plug to a release that still supports Elixir ~> 1.12 (newer Plug
      # starts `PartitionSupervisor`, a 1.14+ module). Only constrains the
      # transitive dep Bypass already pulls; no effect on the runtime API.
      {:plug, "~> 1.15.0", only: :test, override: true},
      {:ex_doc, "~> 0.31", only: :dev, runtime: false},
      {:dialyxir, "~> 1.4", only: [:dev], runtime: false}
    ]
  end

  defp description do
    "Idiomatic Elixir client for the OABP / AIGEN Open Agent Bounty Protocol: " <>
      "mission CRUD, deliverable submission, ecosystem stats and A2A JSON-RPC."
  end

  defp package do
    [
      licenses: ["MIT"],
      maintainers: ["AIGEN Protocol"],
      links: %{
        "GitHub" => @source_url,
        "AIGEN Protocol" => "https://cryptogenesis.duckdns.org"
      },
      files: ~w(lib mix.exs README.md LICENSE .formatter.exs)
    ]
  end

  defp docs do
    [
      main: "OABP",
      extras: ["README.md"],
      source_ref: "v#{@version}",
      source_url: @source_url
    ]
  end
end
