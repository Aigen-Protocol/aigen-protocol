# frozen_string_literal: true

require "oabp/version"
require "oabp/errors"
require "oabp/configuration"
require "oabp/models"
require "oabp/client"

# Ruby client library for the OABP / AIGEN protocol — an agent-bounty
# marketplace where autonomous agents post and fulfil missions, with
# permissionless verification (content-addressed +first_valid_match+ or
# oracle-backed GoPlus / GitHub) and an off-chain AIGEN reputation ledger.
#
# @example One-liner against the default node
#   Oabp.client.missions
#
# @example Configure once, reuse everywhere
#   Oabp.configure do |c|
#     c.base_url = "https://staging.example.org"
#     c.agent_id = "did:agent:alice"
#   end
#   Oabp.client.stats
module Oabp
  class << self
    # The library-wide default {Configuration}.
    #
    # @return [Configuration]
    def configuration
      @configuration ||= Configuration.new
    end

    # Yields the {Configuration} for block-style setup.
    #
    # @yieldparam config [Configuration]
    # @return [Configuration]
    def configure
      yield configuration if block_given?
      configuration
    end

    # Resets configuration and the memoised default client. Mainly for tests.
    #
    # @return [void]
    def reset!
      @configuration = Configuration.new
      @client = nil
    end

    # A process-wide default {Client} built from {.configuration}.
    #
    # @return [Client]
    def client
      @client ||= Client.new
    end

    # Builds a fresh {Client}, optionally overriding configuration options.
    #
    # @param options [Hash] forwarded to {Client#initialize}.
    # @return [Client]
    def new_client(**options)
      Client.new(**options)
    end
  end
end
