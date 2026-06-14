# frozen_string_literal: true

require "oabp"
require "webmock/rspec"

# Block ALL real network connections; every spec must stub its HTTP traffic.
WebMock.disable_net_connect!(allow_localhost: false)

RSpec.configure do |config|
  config.expect_with :rspec do |expectations|
    expectations.include_chain_clauses_in_custom_matcher_descriptions = true
  end

  config.mock_with :rspec do |mocks|
    mocks.verify_partial_doubles = true
  end

  config.shared_context_metadata_behavior = :apply_to_host_groups
  config.disable_monkey_patching!
  config.order = :random
  Kernel.srand config.seed

  # Each example gets a pristine library configuration.
  config.before do
    Oabp.reset!
  end
end

# Shared helpers available to every spec.
module OabpSpecHelpers
  BASE_URL = "https://oabp.test"

  def base_url
    BASE_URL
  end

  def client(**opts)
    Oabp::Client.new(base_url: base_url, **opts)
  end

  def json(body)
    { status: 200, body: JSON.generate(body), headers: { "Content-Type" => "application/json" } }
  end

  def error_response(status, body = { "error" => "boom" })
    { status: status, body: JSON.generate(body), headers: { "Content-Type" => "application/json" } }
  end

  def sample_mission(overrides = {})
    {
      "id" => "m_001",
      "title" => "Find a safe token",
      "description" => "Submit an ERC-20 that passes GoPlus",
      "reward" => { "amount" => 250, "currency" => "AIGEN" },
      "verification_type" => "oracle",
      "verification_params" => { "oracle_description" => "GoPlus safety review" },
      "deadline" => 1_924_905_600,
      "status" => "open",
      "creator_agent_id" => "did:agent:alice",
      "submissions" => []
    }.merge(overrides)
  end
end

RSpec.configure do |config|
  config.include OabpSpecHelpers
end
