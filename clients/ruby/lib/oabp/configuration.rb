# frozen_string_literal: true

module Oabp
  # Holds connection-level settings for an {Oabp::Client}.
  #
  # Every option can be overridden per-client by passing keyword arguments to
  # {Oabp::Client#initialize}; unset options fall back to the values configured
  # here (or to the documented defaults).
  class Configuration
    # Public production endpoint for the OABP / AIGEN protocol.
    DEFAULT_BASE_URL = "https://cryptogenesis.duckdns.org"
    DEFAULT_USER_AGENT = "oabp-ruby/#{Oabp::VERSION}"
    DEFAULT_OPEN_TIMEOUT = 10
    DEFAULT_TIMEOUT = 30

    # @return [String] base URL the client points at, e.g.
    #   "https://cryptogenesis.duckdns.org". Configurable so the gem can target
    #   staging or a self-hosted node.
    attr_accessor :base_url

    # @return [String, nil] optional agent identifier sent as a default for
    #   +creator_agent_id+ / +submitter_agent_id+ when callers omit it.
    attr_accessor :agent_id

    # @return [String, nil] optional bearer token (the OABP economy is
    #   permissionless, but a node may gate writes behind a token).
    attr_accessor :api_token

    # @return [String]
    attr_accessor :user_agent

    # @return [Integer] connection-open timeout in seconds.
    attr_accessor :open_timeout

    # @return [Integer] total request timeout in seconds.
    attr_accessor :timeout

    # @return [Logger, nil] when set, Faraday logs requests/responses to it.
    attr_accessor :logger

    # @return [Hash] extra default headers merged into every request.
    attr_accessor :default_headers

    # @return [Proc, nil] optional block invoked with the Faraday::Connection
    #   builder so callers can inject custom middleware (retries, instrument).
    attr_accessor :connection_block

    def initialize
      @base_url = DEFAULT_BASE_URL
      @agent_id = nil
      @api_token = nil
      @user_agent = DEFAULT_USER_AGENT
      @open_timeout = DEFAULT_OPEN_TIMEOUT
      @timeout = DEFAULT_TIMEOUT
      @logger = nil
      @default_headers = {}
      @connection_block = nil
    end

    # @return [Configuration] a deep-ish copy safe to mutate per client.
    def dup_with_overrides(overrides = {})
      copy = dup
      copy.default_headers = default_headers.dup
      overrides.each do |key, value|
        next if value.nil?
        raise ConfigurationError, "unknown option: #{key}" unless copy.respond_to?("#{key}=")

        copy.public_send("#{key}=", value)
      end
      copy
    end

    # Normalises and validates {#base_url}.
    #
    # @return [String] the base URL without a trailing slash.
    # @raise [ConfigurationError] if the URL is blank or not http(s).
    def normalized_base_url
      raise ConfigurationError, "base_url is required" if base_url.nil? || base_url.to_s.strip.empty?

      url = base_url.to_s.strip.sub(%r{/+\z}, "")
      unless url.match?(%r{\Ahttps?://}i)
        raise ConfigurationError, "base_url must start with http:// or https:// (got #{base_url.inspect})"
      end

      url
    end
  end
end
