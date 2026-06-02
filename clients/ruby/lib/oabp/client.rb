# frozen_string_literal: true

require "json"
require "securerandom"
require "faraday"

module Oabp
  # Ruby client for the OABP / AIGEN protocol agent-bounty marketplace.
  #
  # Wraps the HTTP + A2A JSON-RPC API exposed at the configured +base_url+
  # (default {Oabp::Configuration::DEFAULT_BASE_URL}) and returns immutable
  # value objects from {Oabp::Models}.
  #
  # @example List open missions
  #   client = Oabp::Client.new
  #   client.missions.each { |m| puts "#{m.id}: #{m.title} (#{m.reward})" }
  #
  # @example Create a mission and submit to it
  #   mission = client.create_mission(
  #     creator_agent_id: "did:agent:alice",
  #     title: "Find a safe ERC-20",
  #     description: "Submit a token address that passes GoPlus security review",
  #     reward_amount: 250,
  #     reward_currency: "AIGEN",
  #     verification_type: "oracle",
  #     verification_params: { oracle_description: "GoPlus token-security safety review" },
  #     deadline_hours: 48
  #   )
  #   result = client.submit(mission.id, proof: "0xdAC17F958D2ee523a2206206994597C13D831ec7",
  #                          submitter_agent_id: "did:agent:bob")
  #   puts result.accepted?
  class Client
    # @return [Configuration] the effective, per-client configuration.
    attr_reader :config

    # @param base_url [String, nil] overrides {Configuration#base_url}.
    # @param agent_id [String, nil] default agent id for create/submit calls.
    # @param api_token [String, nil] optional bearer token.
    # @param config [Configuration, nil] a base configuration to copy from;
    #   defaults to {Oabp.configuration}.
    # @param options [Hash] any other {Configuration} accessor (timeout,
    #   logger, user_agent, default_headers, connection_block, ...).
    def initialize(base_url: nil, agent_id: nil, api_token: nil, config: nil, **options)
      base = config || Oabp.configuration
      @config = base.dup_with_overrides(
        { base_url: base_url, agent_id: agent_id, api_token: api_token }.merge(options)
      )
      # Validate eagerly so a bad base_url fails at construction, not first call.
      @config.normalized_base_url
      @connection = build_connection
    end

    # -- Missions: read -------------------------------------------------------

    # Lists open missions. +GET /api/missions+.
    #
    # @return [Array<Oabp::Models::Mission>]
    def missions
      body = request(:get, "/api/missions")
      array_from(body, "missions").map { |h| Models::Mission.from_hash(h) }
    end
    alias list_missions missions

    # Fetches one mission by id, including submissions and resolution.
    # +GET /api/missions/{id}+.
    #
    # @param id [String, Integer]
    # @return [Oabp::Models::Mission]
    # @raise [Oabp::NotFoundError] when the mission does not exist.
    def mission(id)
      validate_present!(id, "id")
      body = request(:get, "/api/missions/#{encode(id)}")
      Models::Mission.from_hash(unwrap(body, "mission"))
    end
    alias get_mission mission

    # -- Missions: write ------------------------------------------------------

    # Creates a mission. +POST /api/missions+.
    #
    # @param title [String]
    # @param description [String]
    # @param reward_amount [Numeric]
    # @param verification_type [String] one of
    #   {Oabp::Models::Mission::VERIFICATION_TYPES}.
    # @param deadline_hours [Numeric] hours from now until the deadline.
    # @param creator_agent_id [String, nil] falls back to {Configuration#agent_id}.
    # @param reward_currency [String] "AIGEN" (default) or "USDC".
    # @param verification_params [Hash] e.g. +{ regex: "..." }+ or
    #   +{ oracle_description: "..." }+.
    # @return [Oabp::Models::Mission] the created mission.
    def create_mission(title:, description:, reward_amount:, verification_type:,
                       deadline_hours:, creator_agent_id: nil, reward_currency: "AIGEN",
                       verification_params: {})
      agent = creator_agent_id || config.agent_id
      validate_present!(agent, "creator_agent_id")
      validate_present!(title, "title")
      validate_verification_type!(verification_type)
      validate_positive!(reward_amount, "reward_amount")
      validate_positive!(deadline_hours, "deadline_hours")

      payload = {
        creator_agent_id: agent,
        title: title,
        description: description,
        reward_amount: reward_amount,
        reward_currency: reward_currency,
        verification_type: verification_type,
        verification_params: verification_params || {},
        deadline_hours: deadline_hours
      }
      body = request(:post, "/api/missions", body: payload)
      Models::Mission.from_hash(unwrap(body, "mission"))
    end

    # Submits a deliverable to a mission. +POST /missions/{id}/submit+.
    #
    # The +proof+ is free text or a URL. For +first_valid_match+ missions it is
    # matched against the mission's regex (content-addressed); for +oracle+
    # missions it is verified for real (GoPlus / GitHub).
    #
    # @param mission_id [String, Integer]
    # @param proof [String]
    # @param submitter_agent_id [String, nil] falls back to {Configuration#agent_id}.
    # @return [Oabp::Models::SubmissionResult]
    def submit(mission_id, proof:, submitter_agent_id: nil)
      validate_present!(mission_id, "mission_id")
      validate_present!(proof, "proof")
      agent = submitter_agent_id || config.agent_id
      validate_present!(agent, "submitter_agent_id")

      payload = { submitter_agent_id: agent, proof: proof }
      body = request(:post, "/missions/#{encode(mission_id)}/submit", body: payload)
      result = Models::SubmissionResult.from_hash(unwrap(body, "result"))
      # Ensure mission_id is populated even if the server omits it.
      if result.mission_id.nil?
        Models::SubmissionResult.from_hash(
          (result.raw || {}).merge("mission_id" => mission_id, "submitter_agent_id" => agent)
        )
      else
        result
      end
    end
    alias submit_deliverable submit

    # -- Stats & reputation ---------------------------------------------------

    # Protocol-wide statistics. +GET /api/stats+.
    #
    # @return [Oabp::Models::Stats]
    def stats
      body = request(:get, "/api/stats")
      Models::Stats.from_hash(unwrap(body, "stats"))
    end

    # Reputation snapshot for an agent.
    #
    # Tries a dedicated +GET /api/agents/{id}/reputation+ endpoint when the node
    # exposes one; otherwise derives a view by scanning missions the agent
    # created/won/submitted to (the AIGEN ledger is the protocol's reputation).
    #
    # @param agent_id [String, nil] falls back to {Configuration#agent_id}.
    # @return [Oabp::Models::Reputation]
    def reputation(agent_id = nil)
      agent = agent_id || config.agent_id
      validate_present!(agent, "agent_id")

      body = request(:get, "/api/agents/#{encode(agent)}/reputation", allow_not_found: true)
      return Models::Reputation.from_hash(unwrap(body, "reputation")) unless body.nil?

      derive_reputation(agent)
    end

    # -- A2A JSON-RPC ---------------------------------------------------------

    # Performs a raw A2A JSON-RPC 2.0 call. +POST /api/a2a+.
    #
    # @param method [String] e.g. "message/send", "tasks/get", "tasks/list".
    # @param params [Hash]
    # @param id [String, Integer, nil] request id; a UUID is generated if nil.
    # @return [Oabp::Models::A2AResult]
    # @raise [Oabp::ApiError] when the JSON-RPC response carries an +error+.
    def a2a(method, params = {}, id: nil)
      validate_present!(method, "method")
      rpc_id = id || SecureRandom.uuid
      payload = { jsonrpc: "2.0", id: rpc_id, method: method, params: params }
      body = request(:post, "/api/a2a", body: payload)
      result = Models::A2AResult.from_hash(body.is_a?(Hash) ? body : { "result" => body })
      raise_a2a_error!(result) if result.error?

      result
    end

    # A2A convenience: send a message to the agent. ("message/send")
    #
    # @param text [String] the message text.
    # @param role [String] sender role, default "user".
    # @param extra [Hash] extra params merged into the JSON-RPC params.
    # @return [Oabp::Models::A2AResult]
    def send_message(text, role: "user", **extra)
      message = {
        role: role,
        parts: [{ kind: "text", text: text }],
        messageId: SecureRandom.uuid
      }
      a2a("message/send", { message: message }.merge(extra))
    end

    # A2A convenience: fetch a task by id. ("tasks/get")
    #
    # @param task_id [String]
    # @return [Oabp::Models::A2AResult]
    def get_task(task_id)
      validate_present!(task_id, "task_id")
      a2a("tasks/get", { id: task_id })
    end

    # A2A convenience: list tasks. ("tasks/list")
    #
    # @return [Oabp::Models::A2AResult]
    def list_tasks(**params)
      a2a("tasks/list", params)
    end

    # Fetches the agent card. +GET /.well-known/agent-card.json+ (ES256-signed).
    #
    # @return [Hash] the raw card document.
    def agent_card
      request(:get, "/.well-known/agent-card.json")
    end

    # Fetches the JWKS used to verify the agent card. +GET /.well-known/jwks.json+.
    #
    # @return [Hash]
    def jwks
      request(:get, "/.well-known/jwks.json")
    end

    private

    # -- HTTP plumbing --------------------------------------------------------

    def build_connection
      Faraday.new(url: config.normalized_base_url) do |f|
        f.request :json
        f.options.open_timeout = config.open_timeout
        f.options.timeout = config.timeout
        apply_headers(f)
        f.response :logger, config.logger if config.logger
        config.connection_block&.call(f)
        f.adapter Faraday.default_adapter
      end
    end

    def apply_headers(faraday)
      faraday.headers["User-Agent"] = config.user_agent
      faraday.headers["Accept"] = "application/json"
      faraday.headers["Authorization"] = "Bearer #{config.api_token}" if config.api_token
      config.default_headers.each { |key, value| faraday.headers[key.to_s] = value }
    end

    # Issues a request and returns the parsed body, or raises a typed error.
    #
    # @param allow_not_found [Boolean] when true, a 404 returns nil instead of
    #   raising (used for optional/derived endpoints).
    def request(method, path, body: nil, allow_not_found: false)
      response =
        begin
          @connection.run_request(method, path, body && JSON.generate(body), nil)
        rescue Faraday::TimeoutError => e
          raise ConnectionError, "request timed out: #{e.message}"
        rescue Faraday::ConnectionFailed => e
          raise ConnectionError, "could not connect to #{config.base_url}: #{e.message}"
        rescue Faraday::Error => e
          raise ConnectionError, "transport error: #{e.message}"
        end

      handle_response(response, method, path, allow_not_found: allow_not_found)
    end

    def handle_response(response, method, path, allow_not_found:)
      status = response.status
      parsed = parse_body(response.body)

      return parsed if status.between?(200, 299)
      return nil if status == 404 && allow_not_found

      raise ErrorFactory.build(
        status: status, body: parsed, request_method: method, path: path
      )
    end

    def parse_body(raw)
      return nil if raw.nil? || raw == ""
      return raw unless raw.is_a?(String)

      JSON.parse(raw)
    rescue JSON::ParserError
      # Non-JSON body (e.g. an HTML error page): hand back the raw string.
      raw
    end

    # -- Response shaping -----------------------------------------------------

    # Extracts an array from a response that may be a bare array or an
    # +{ "<key>": [...] }+ / +{ "data": [...] }+ envelope.
    def array_from(body, key)
      return body if body.is_a?(Array)
      return [] if body.nil?

      if body.is_a?(Hash)
        candidate = body[key] || body["data"] || body["items"]
        return candidate if candidate.is_a?(Array)
      end
      raise ApiError.new(
        "expected an array of #{key} but got #{body.class}",
        body: body
      )
    end

    # Unwraps a single object from a possible +{ "<key>": {...} }+ envelope.
    def unwrap(body, key)
      return {} if body.nil?
      return body unless body.is_a?(Hash)

      nested = body[key] || body["data"]
      nested.is_a?(Hash) ? nested : body
    end

    def derive_reputation(agent)
      created = 0
      won = 0
      submitted = 0
      balance = 0.0

      missions.each do |m|
        created += 1 if m.creator_agent_id == agent
        if m.resolution && m.resolution.winner_agent_id == agent
          won += 1
          balance += m.resolution.reward_paid.to_f
        end
        submitted += 1 if m.submissions.any? { |s| s.submitter_agent_id == agent }
      end

      Models::Reputation.from_hash(
        "agent_id" => agent,
        "aigen_balance" => balance,
        "missions_created" => created,
        "missions_won" => won,
        "submissions_made" => submitted
      )
    end

    def raise_a2a_error!(result)
      err = result.error
      message = err.is_a?(Hash) ? (err["message"] || err.inspect) : err.to_s
      code = err.is_a?(Hash) ? err["code"] : nil
      label = code ? "A2A error (#{code})" : "A2A error"
      raise ApiError.new(
        "#{label}: #{message}",
        body: result.raw,
        request_method: :post,
        path: "/api/a2a"
      )
    end

    # -- Validation helpers ---------------------------------------------------

    def encode(value)
      require "erb"
      ERB::Util.url_encode(value.to_s)
    end

    def validate_present!(value, name)
      return unless value.nil? || value.to_s.strip.empty?

      raise ValidationError, "#{name} is required"
    end

    def validate_positive!(value, name)
      num = Float(value)
      raise ValidationError, "#{name} must be greater than 0" unless num.positive?
    rescue ArgumentError, TypeError
      raise ValidationError, "#{name} must be a number"
    end

    def validate_verification_type!(type)
      return if Models::Mission::VERIFICATION_TYPES.include?(type.to_s)

      raise ValidationError,
            "verification_type must be one of #{Models::Mission::VERIFICATION_TYPES.join(', ')} (got #{type.inspect})"
    end
  end
end
