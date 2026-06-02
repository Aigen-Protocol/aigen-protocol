# frozen_string_literal: true

module Oabp
  # Immutable value objects returned by {Oabp::Client}.
  #
  # Every object is built from a parsed JSON +Hash+ via +from_hash+, exposes
  # typed reader methods, keeps the untouched payload in {#raw} for
  # forward-compatibility, and compares by value. Unknown/extra JSON keys are
  # preserved in {#raw} and never raise.
  module Models
    # Shared behaviour for all value objects: value equality, hash-ability and
    # a useful +inspect+.
    module ValueObject
      def ==(other)
        other.is_a?(self.class) && other.to_h == to_h
      end
      alias eql? ==

      def hash
        [self.class, to_h].hash
      end

      def inspect
        fields = to_h.map { |k, v| "#{k}=#{v.inspect}" }.join(", ")
        "#<#{self.class.name} #{fields}>"
      end
    end

    # A reward attached to a mission, e.g. 250 AIGEN or 5 USDC.
    class Reward
      include ValueObject

      attr_reader :amount, :currency, :raw

      def self.from_hash(hash)
        hash ||= {}
        new(
          amount: numeric(hash["amount"]),
          currency: hash["currency"],
          raw: hash
        )
      end

      def self.numeric(value)
        return nil if value.nil?
        return value if value.is_a?(Numeric)

        Float(value)
      rescue ArgumentError, TypeError
        value
      end

      def initialize(amount:, currency:, raw: {})
        @amount = amount
        @currency = currency
        @raw = raw
        freeze
      end

      def aigen?
        currency.to_s.casecmp("AIGEN").zero?
      end

      def usdc?
        currency.to_s.casecmp("USDC").zero?
      end

      def to_h
        { amount: amount, currency: currency }
      end

      def to_s
        "#{amount} #{currency}"
      end
    end

    # A single deliverable submitted against a mission.
    class Submission
      include ValueObject

      attr_reader :submitter_agent_id, :proof, :status, :submitted_at, :raw

      def self.from_hash(hash)
        hash ||= {}
        new(
          submitter_agent_id: hash["submitter_agent_id"] || hash["submitter"],
          proof: hash["proof"],
          status: hash["status"],
          submitted_at: Models.parse_time(hash["submitted_at"] || hash["created_at"]),
          raw: hash
        )
      end

      def initialize(submitter_agent_id:, proof:, status: nil, submitted_at: nil, raw: {})
        @submitter_agent_id = submitter_agent_id
        @proof = proof
        @status = status
        @submitted_at = submitted_at
        @raw = raw
        freeze
      end

      def accepted?
        %w[accepted valid verified paid winner].include?(status.to_s.downcase)
      end

      def to_h
        {
          submitter_agent_id: submitter_agent_id,
          proof: proof,
          status: status,
          submitted_at: submitted_at
        }
      end
    end

    # The outcome of a resolved mission (who won, how it was verified).
    class Resolution
      include ValueObject

      attr_reader :winner_agent_id, :winning_proof, :verified_by, :resolved_at, :reward_paid, :raw

      def self.from_hash(hash)
        return nil if hash.nil? || hash.empty?

        new(
          winner_agent_id: hash["winner_agent_id"] || hash["winner"],
          winning_proof: hash["winning_proof"] || hash["proof"],
          verified_by: hash["verified_by"] || hash["verification_type"],
          resolved_at: Models.parse_time(hash["resolved_at"]),
          reward_paid: Reward.numeric(hash["reward_paid"] || hash["amount"]),
          raw: hash
        )
      end

      def initialize(winner_agent_id:, winning_proof:, verified_by:, resolved_at:, reward_paid:, raw: {})
        @winner_agent_id = winner_agent_id
        @winning_proof = winning_proof
        @verified_by = verified_by
        @resolved_at = resolved_at
        @reward_paid = reward_paid
        @raw = raw
        freeze
      end

      def to_h
        {
          winner_agent_id: winner_agent_id,
          winning_proof: winning_proof,
          verified_by: verified_by,
          resolved_at: resolved_at,
          reward_paid: reward_paid
        }
      end
    end

    # A bounty mission on the OABP marketplace.
    class Mission
      include ValueObject

      # Recognised verification strategies.
      VERIFICATION_TYPES = %w[
        first_valid_match oracle peer_vote creator_judges
      ].freeze

      attr_reader :id, :title, :description, :reward, :verification_type,
                  :verification_params, :deadline, :status, :creator_agent_id,
                  :submissions, :resolution, :raw

      def self.from_hash(hash)
        hash ||= {}
        new(
          id: hash["id"],
          title: hash["title"],
          description: hash["description"],
          reward: Reward.from_hash(hash["reward"] || reward_from_flat(hash)),
          verification_type: hash["verification_type"],
          verification_params: hash["verification_params"] || {},
          deadline: Models.parse_time(hash["deadline"]),
          status: hash["status"],
          creator_agent_id: hash["creator_agent_id"],
          submissions: Array(hash["submissions"]).map { |s| Submission.from_hash(s) },
          resolution: Resolution.from_hash(hash["resolution"]),
          raw: hash
        )
      end

      # Some endpoints return reward as flat +reward_amount+/+reward_currency+.
      def self.reward_from_flat(hash)
        return nil unless hash.key?("reward_amount") || hash.key?("reward_currency")

        { "amount" => hash["reward_amount"], "currency" => hash["reward_currency"] }
      end

      def initialize(id:, title:, description:, reward:, verification_type:,
                     verification_params:, deadline:, status:, creator_agent_id:,
                     submissions:, resolution:, raw: {})
        @id = id
        @title = title
        @description = description
        @reward = reward
        @verification_type = verification_type
        @verification_params = verification_params
        @deadline = deadline
        @status = status
        @creator_agent_id = creator_agent_id
        @submissions = submissions.freeze
        @resolution = resolution
        @raw = raw
        freeze
      end

      def open?
        status.to_s.downcase == "open"
      end

      def resolved?
        status.to_s.downcase == "resolved" || !resolution.nil?
      end

      def oracle?
        verification_type == "oracle"
      end

      def first_valid_match?
        verification_type == "first_valid_match"
      end

      # @return [Regexp, nil] compiled matcher for +first_valid_match+ missions.
      def regex
        pattern = verification_params && verification_params["regex"]
        return nil if pattern.nil? || pattern.to_s.empty?

        Regexp.new(pattern)
      rescue RegexpError
        nil
      end

      # @return [Boolean, nil] true if +proof+ would satisfy a
      #   +first_valid_match+ mission's regex. nil when not applicable.
      #
      # Tri-state on purpose: nil distinguishes "this is not a regex mission"
      # from a genuine false (proof present but does not match).
      # rubocop:disable Style/ReturnNilInPredicateMethodDefinition
      def proof_matches?(proof)
        rx = regex
        return nil if rx.nil?

        !rx.match(proof.to_s).nil?
      end
      # rubocop:enable Style/ReturnNilInPredicateMethodDefinition

      def expired?(now = Time.now)
        return false if deadline.nil?

        deadline < now
      end

      def to_h
        {
          id: id,
          title: title,
          description: description,
          reward: reward&.to_h,
          verification_type: verification_type,
          verification_params: verification_params,
          deadline: deadline,
          status: status,
          creator_agent_id: creator_agent_id,
          submissions: submissions.map(&:to_h),
          resolution: resolution&.to_h
        }
      end
    end

    # Protocol-wide statistics from +GET /api/stats+.
    class Stats
      include ValueObject

      attr_reader :resolved, :open, :lifetime_reward_aigen_paid, :raw

      def self.from_hash(hash)
        hash ||= {}
        new(
          resolved: integer(hash["resolved"]),
          open: integer(hash["open"]),
          lifetime_reward_aigen_paid: Reward.numeric(hash["lifetime_reward_aigen_paid"]),
          raw: hash
        )
      end

      def self.integer(value)
        return nil if value.nil?

        Integer(value)
      rescue ArgumentError, TypeError
        value
      end

      def initialize(resolved:, open:, lifetime_reward_aigen_paid:, raw: {})
        @resolved = resolved
        @open = open
        @lifetime_reward_aigen_paid = lifetime_reward_aigen_paid
        @raw = raw
        freeze
      end

      def total
        return nil if resolved.nil? || open.nil?

        resolved + open
      end

      def to_h
        {
          resolved: resolved,
          open: open,
          lifetime_reward_aigen_paid: lifetime_reward_aigen_paid
        }
      end
    end

    # An agent's reputation snapshot (AIGEN balance + activity counters).
    #
    # The protocol's reputation is the off-chain AIGEN points ledger; this view
    # derives an agent's balance and mission counts from +/api/stats+-style data
    # or a dedicated reputation endpoint when the node exposes one.
    class Reputation
      include ValueObject

      attr_reader :agent_id, :aigen_balance, :missions_created,
                  :missions_won, :submissions_made, :raw

      def self.from_hash(hash)
        hash ||= {}
        new(
          agent_id: hash["agent_id"] || hash["id"],
          aigen_balance: Reward.numeric(hash["aigen_balance"] || hash["balance"] || hash["aigen"]),
          missions_created: Stats.integer(hash["missions_created"]),
          missions_won: Stats.integer(hash["missions_won"]),
          submissions_made: Stats.integer(hash["submissions_made"]),
          raw: hash
        )
      end

      def initialize(agent_id:, aigen_balance:, missions_created:, missions_won:, submissions_made:, raw: {})
        @agent_id = agent_id
        @aigen_balance = aigen_balance
        @missions_created = missions_created
        @missions_won = missions_won
        @submissions_made = submissions_made
        @raw = raw
        freeze
      end

      def to_h
        {
          agent_id: agent_id,
          aigen_balance: aigen_balance,
          missions_created: missions_created,
          missions_won: missions_won,
          submissions_made: submissions_made
        }
      end
    end

    # The result of submitting a deliverable to a mission.
    class SubmissionResult
      include ValueObject

      attr_reader :mission_id, :submitter_agent_id, :accepted, :status,
                  :verified, :reward_paid, :message, :raw

      ACCEPTED_STATES = %w[accepted valid verified paid winner].freeze

      def self.from_hash(hash)
        hash ||= {}
        status = hash["status"]
        new(
          mission_id: hash["mission_id"] || hash["id"],
          submitter_agent_id: hash["submitter_agent_id"],
          accepted: derive_accepted(hash["accepted"], status),
          status: status,
          verified: truthy(hash["verified"]),
          reward_paid: Reward.numeric(hash["reward_paid"] || hash["amount"]),
          message: hash["message"] || hash["detail"],
          raw: hash
        )
      end

      # Honour an explicit +accepted+ flag; otherwise infer it from +status+.
      # Returns nil only when neither field carries information.
      def self.derive_accepted(flag, status)
        explicit = truthy(flag)
        return explicit unless explicit.nil?
        return nil if status.nil?

        ACCEPTED_STATES.include?(status.to_s.downcase)
      end

      def self.truthy(value)
        return nil if value.nil?
        return value if [true, false].include?(value)

        ACCEPTED_STATES.include?(value.to_s.downcase) || value.to_s.casecmp("true").zero?
      end

      def initialize(mission_id:, submitter_agent_id:, accepted:, status:, verified:, reward_paid:, message:, raw: {})
        @mission_id = mission_id
        @submitter_agent_id = submitter_agent_id
        @accepted = accepted
        @status = status
        @verified = verified
        @reward_paid = reward_paid
        @message = message
        @raw = raw
        freeze
      end

      def accepted?
        accepted == true
      end

      def to_h
        {
          mission_id: mission_id,
          submitter_agent_id: submitter_agent_id,
          accepted: accepted,
          status: status,
          verified: verified,
          reward_paid: reward_paid,
          message: message
        }
      end
    end

    # The response envelope from an A2A JSON-RPC call.
    class A2AResult
      include ValueObject

      attr_reader :id, :result, :error, :raw

      def self.from_hash(hash)
        hash ||= {}
        new(
          id: hash["id"],
          result: hash["result"],
          error: hash["error"],
          raw: hash
        )
      end

      def initialize(id:, result:, error:, raw: {})
        @id = id
        @result = result
        @error = error
        @raw = raw
        freeze
      end

      def error?
        !error.nil?
      end

      def to_h
        { id: id, result: result, error: error }
      end
    end

    module_function

    # Parses a unix-seconds integer or ISO-8601 string into a +Time+.
    #
    # @param value [Integer, String, nil]
    # @return [Time, nil] returns the original value if it cannot be parsed.
    def parse_time(value)
      return nil if value.nil?
      return value if value.is_a?(Time)

      if value.is_a?(Numeric) || value.to_s.match?(/\A\d+\z/)
        Time.at(value.to_i).utc
      else
        Time.parse(value.to_s).utc
      end
    rescue ArgumentError, TypeError
      value
    end
  end
end
