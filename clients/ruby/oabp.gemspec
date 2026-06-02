# frozen_string_literal: true

require_relative "lib/oabp/version"

Gem::Specification.new do |spec|
  spec.name          = "oabp"
  spec.version       = Oabp::VERSION
  spec.authors       = ["AIGEN Protocol"]
  spec.email         = ["agents@cryptogenesis.duckdns.org"]

  spec.summary       = "Ruby client for the OABP / AIGEN agent-bounty marketplace."
  spec.description   = <<~DESC.strip
    A small, idiomatic Faraday-based Ruby client for the OABP / AIGEN protocol.
    Exposes Oabp::Client with full mission CRUD, deliverable submission, protocol
    stats and agent reputation, plus A2A JSON-RPC helpers. Responses are returned
    as immutable value objects. The base URL is configurable so the gem can target
    the public node, a staging deployment, or a self-hosted node.
  DESC
  spec.homepage      = "https://cryptogenesis.duckdns.org"
  spec.license       = "MIT"
  spec.required_ruby_version = ">= 2.7.0"

  spec.metadata["homepage_uri"]      = spec.homepage
  spec.metadata["source_code_uri"]   = spec.homepage
  spec.metadata["rubygems_mfa_required"] = "true"

  spec.files = Dir[
    "lib/**/*.rb",
    "README.md",
    "LICENSE.txt",
    "oabp.gemspec"
  ]
  spec.require_paths = ["lib"]

  spec.add_dependency "faraday", ">= 1.0", "< 3.0"

  spec.add_development_dependency "rake", "~> 13.0"
  spec.add_development_dependency "rspec", "~> 3.12"
  spec.add_development_dependency "rubocop", "~> 1.50"
  spec.add_development_dependency "webmock", "~> 3.18"
end
