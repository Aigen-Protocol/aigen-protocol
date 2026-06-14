# frozen_string_literal: true

require "spec_helper"

RSpec.describe Oabp::Models do
  describe Oabp::Models::Reward do
    it "parses amount and currency and exposes predicates" do
      reward = described_class.from_hash("amount" => "250.5", "currency" => "AIGEN")
      expect(reward.amount).to eq(250.5)
      expect(reward).to be_aigen
      expect(reward).not_to be_usdc
      expect(reward.to_s).to eq("250.5 AIGEN")
    end

    it "is frozen and value-comparable" do
      a = described_class.from_hash("amount" => 5, "currency" => "USDC")
      b = described_class.from_hash("amount" => 5, "currency" => "USDC")
      expect(a).to be_frozen
      expect(a).to eq(b)
      expect(a.hash).to eq(b.hash)
      expect(a).to be_usdc
    end

    it "keeps a non-numeric amount intact instead of raising" do
      reward = described_class.from_hash("amount" => "lots", "currency" => "AIGEN")
      expect(reward.amount).to eq("lots")
    end
  end

  describe Oabp::Models::Mission do
    subject(:mission) { described_class.from_hash(payload) }

    let(:payload) do
      {
        "id" => "m_1",
        "title" => "T",
        "description" => "D",
        "reward" => { "amount" => 100, "currency" => "AIGEN" },
        "verification_type" => "first_valid_match",
        "verification_params" => { "regex" => "0x[a-fA-F0-9]{40}" },
        "deadline" => 1_924_905_600,
        "status" => "open",
        "creator_agent_id" => "did:agent:alice",
        "submissions" => [
          { "submitter_agent_id" => "did:agent:bob", "proof" => "x", "status" => "pending" }
        ]
      }
    end

    it "exposes typed fields and nested value objects" do
      expect(mission.id).to eq("m_1")
      expect(mission.reward).to be_a(Oabp::Models::Reward)
      expect(mission.reward.amount).to eq(100)
      expect(mission.submissions.first).to be_a(Oabp::Models::Submission)
      expect(mission.submissions.first.submitter_agent_id).to eq("did:agent:bob")
    end

    it "parses the unix deadline into UTC time" do
      expect(mission.deadline).to be_a(Time)
      expect(mission.deadline.utc?).to be(true)
      expect(mission.deadline.to_i).to eq(1_924_905_600)
    end

    it "answers status predicates" do
      expect(mission).to be_open
      expect(mission).not_to be_resolved
      expect(mission).to be_first_valid_match
      expect(mission).not_to be_oracle
    end

    it "compiles the verification regex and matches proofs" do
      expect(mission.regex).to be_a(Regexp)
      expect(mission.proof_matches?("0xdAC17F958D2ee523a2206206994597C13D831ec7")).to be(true)
      expect(mission.proof_matches?("not-an-address")).to be(false)
    end

    it "returns nil for proof_matches? on non-regex missions" do
      m = described_class.from_hash(payload.merge("verification_type" => "oracle",
                                                  "verification_params" => {}))
      expect(m.proof_matches?("anything")).to be_nil
    end

    it "detects expiry relative to a clock" do
      past = described_class.from_hash(payload.merge("deadline" => 100))
      expect(past.expired?(Time.at(200))).to be(true)
      expect(mission.expired?(Time.at(0))).to be(false)
    end

    it "supports the flat reward_amount/reward_currency shape" do
      flat = described_class.from_hash(
        "id" => "m_2", "reward_amount" => 9, "reward_currency" => "USDC"
      )
      expect(flat.reward.amount).to eq(9)
      expect(flat.reward).to be_usdc
    end

    it "reads resolution and marks the mission resolved" do
      resolved = described_class.from_hash(
        payload.merge(
          "status" => "resolved",
          "resolution" => {
            "winner_agent_id" => "did:agent:bob",
            "winning_proof" => "0xabc",
            "verified_by" => "oracle",
            "reward_paid" => 100
          }
        )
      )
      expect(resolved).to be_resolved
      expect(resolved.resolution).to be_a(Oabp::Models::Resolution)
      expect(resolved.resolution.winner_agent_id).to eq("did:agent:bob")
      expect(resolved.resolution.reward_paid).to eq(100)
    end

    it "tolerates a bad regex without raising" do
      m = described_class.from_hash(
        payload.merge("verification_params" => { "regex" => "(" })
      )
      expect(m.regex).to be_nil
      expect(m.proof_matches?("x")).to be_nil
    end

    it "keeps the raw payload for forward compatibility" do
      m = described_class.from_hash(payload.merge("future_field" => 42))
      expect(m.raw["future_field"]).to eq(42)
    end
  end

  describe Oabp::Models::Stats do
    it "parses counters and computes the total" do
      stats = described_class.from_hash(
        "resolved" => "12", "open" => 3, "lifetime_reward_aigen_paid" => "108000.5"
      )
      expect(stats.resolved).to eq(12)
      expect(stats.open).to eq(3)
      expect(stats.total).to eq(15)
      expect(stats.lifetime_reward_aigen_paid).to eq(108_000.5)
    end
  end

  describe Oabp::Models::SubmissionResult do
    it "coerces accepted/verified from strings" do
      res = described_class.from_hash(
        "mission_id" => "m_1", "status" => "accepted", "verified" => "true", "reward_paid" => 250
      )
      expect(res).to be_accepted
      expect(res.verified).to be(true)
      expect(res.reward_paid).to eq(250)
    end

    it "handles a rejected submission" do
      res = described_class.from_hash("status" => "rejected", "accepted" => false)
      expect(res).not_to be_accepted
    end
  end

  describe ".parse_time" do
    it "handles unix integers, iso strings, and passthrough" do
      expect(described_class.parse_time(1_924_905_600)).to be_a(Time)
      expect(described_class.parse_time("2031-01-01T00:00:00Z")).to be_a(Time)
      expect(described_class.parse_time(nil)).to be_nil
      expect(described_class.parse_time("garbage")).to eq("garbage")
    end
  end
end
