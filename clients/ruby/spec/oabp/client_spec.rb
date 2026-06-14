# frozen_string_literal: true

require "spec_helper"

RSpec.describe Oabp::Client do
  describe "construction" do
    it "validates the base url eagerly" do
      expect { described_class.new(base_url: "nope") }
        .to raise_error(Oabp::ConfigurationError)
    end

    it "inherits from a passed configuration but overrides per client" do
      base = Oabp::Configuration.new
      base.agent_id = "did:agent:default"
      c = described_class.new(base_url: base_url, config: base, timeout: 7)
      expect(c.config.agent_id).to eq("did:agent:default")
      expect(c.config.timeout).to eq(7)
    end
  end

  describe "#missions" do
    it "GETs /api/missions and returns Mission value objects" do
      stub_request(:get, "#{base_url}/api/missions")
        .to_return(json([sample_mission, sample_mission("id" => "m_002")]))

      missions = client.missions

      expect(missions.size).to eq(2)
      expect(missions).to all(be_a(Oabp::Models::Mission))
      expect(missions.first.id).to eq("m_001")
      expect(missions.first.reward.amount).to eq(250)
    end

    it "unwraps a { missions: [...] } envelope" do
      stub_request(:get, "#{base_url}/api/missions")
        .to_return(json("missions" => [sample_mission]))
      expect(client.missions.first.id).to eq("m_001")
    end

    it "sends Accept and User-Agent headers" do
      stub = stub_request(:get, "#{base_url}/api/missions")
             .with(headers: { "Accept" => "application/json", "User-Agent" => /oabp-ruby/ })
             .to_return(json([]))
      client.missions
      expect(stub).to have_been_requested
    end
  end

  describe "#mission" do
    it "GETs /api/missions/{id} with submissions and resolution" do
      payload = sample_mission(
        "status" => "resolved",
        "submissions" => [{ "submitter_agent_id" => "did:agent:bob", "proof" => "0xabc", "status" => "accepted" }],
        "resolution" => { "winner_agent_id" => "did:agent:bob", "reward_paid" => 250, "verified_by" => "oracle" }
      )
      stub_request(:get, "#{base_url}/api/missions/m_001").to_return(json(payload))

      mission = client.mission("m_001")

      expect(mission).to be_resolved
      expect(mission.submissions.first).to be_accepted
      expect(mission.resolution.winner_agent_id).to eq("did:agent:bob")
    end

    it "raises NotFoundError on 404" do
      stub_request(:get, "#{base_url}/api/missions/nope")
        .to_return(error_response(404, "error" => "no such mission"))
      expect { client.mission("nope") }
        .to raise_error(Oabp::NotFoundError, /no such mission/)
    end

    it "rejects a blank id without hitting the network" do
      expect { client.mission("") }.to raise_error(Oabp::ValidationError, /id is required/)
    end

    it "url-encodes the id" do
      stub = stub_request(:get, "#{base_url}/api/missions/did%3Aagent%3Ax")
             .to_return(json(sample_mission("id" => "did:agent:x")))
      client.mission("did:agent:x")
      expect(stub).to have_been_requested
    end
  end

  describe "#create_mission" do
    let(:created) { sample_mission("id" => "m_new", "status" => "open") }

    it "POSTs /api/missions with the documented body" do
      stub = stub_request(:post, "#{base_url}/api/missions")
             .with(
               body: {
                 "creator_agent_id" => "did:agent:alice",
                 "title" => "Find a safe token",
                 "description" => "desc",
                 "reward_amount" => 250,
                 "reward_currency" => "AIGEN",
                 "verification_type" => "oracle",
                 "verification_params" => { "oracle_description" => "GoPlus" },
                 "deadline_hours" => 48
               },
               headers: { "Content-Type" => "application/json" }
             )
             .to_return(json(created))

      mission = client.create_mission(
        creator_agent_id: "did:agent:alice",
        title: "Find a safe token",
        description: "desc",
        reward_amount: 250,
        reward_currency: "AIGEN",
        verification_type: "oracle",
        verification_params: { oracle_description: "GoPlus" },
        deadline_hours: 48
      )

      expect(stub).to have_been_requested
      expect(mission.id).to eq("m_new")
    end

    it "falls back to the configured agent id" do
      stub = stub_request(:post, "#{base_url}/api/missions")
             .with(body: hash_including("creator_agent_id" => "did:agent:cfg"))
             .to_return(json(created))

      client(agent_id: "did:agent:cfg").create_mission(
        title: "t", description: "d", reward_amount: 1,
        verification_type: "first_valid_match",
        verification_params: { regex: "x" }, deadline_hours: 1
      )
      expect(stub).to have_been_requested
    end

    it "rejects an unknown verification_type" do
      expect do
        client.create_mission(
          creator_agent_id: "a", title: "t", description: "d",
          reward_amount: 1, verification_type: "magic", deadline_hours: 1
        )
      end.to raise_error(Oabp::ValidationError, /verification_type/)
    end

    it "rejects a non-positive reward" do
      expect do
        client.create_mission(
          creator_agent_id: "a", title: "t", description: "d",
          reward_amount: 0, verification_type: "oracle", deadline_hours: 1
        )
      end.to raise_error(Oabp::ValidationError, /reward_amount/)
    end

    it "requires a creator agent id" do
      expect do
        client.create_mission(
          title: "t", description: "d", reward_amount: 1,
          verification_type: "oracle", deadline_hours: 1
        )
      end.to raise_error(Oabp::ValidationError, /creator_agent_id/)
    end
  end

  describe "#submit" do
    it "POSTs /missions/{id}/submit and returns a SubmissionResult" do
      stub = stub_request(:post, "#{base_url}/missions/m_001/submit")
             .with(body: { "submitter_agent_id" => "did:agent:bob", "proof" => "0xabc" })
             .to_return(json("mission_id" => "m_001", "status" => "accepted",
                             "verified" => true, "reward_paid" => 250))

      result = client.submit("m_001", proof: "0xabc", submitter_agent_id: "did:agent:bob")

      expect(stub).to have_been_requested
      expect(result).to be_accepted
      expect(result.reward_paid).to eq(250)
      expect(result.mission_id).to eq("m_001")
    end

    it "backfills mission_id when the server omits it" do
      stub_request(:post, "#{base_url}/missions/m_001/submit")
        .to_return(json("status" => "rejected"))
      result = client.submit("m_001", proof: "junk", submitter_agent_id: "did:agent:bob")
      expect(result.mission_id).to eq("m_001")
      expect(result).not_to be_accepted
    end

    it "surfaces a 422 as UnprocessableEntityError (proof failed verification)" do
      stub_request(:post, "#{base_url}/missions/m_001/submit")
        .to_return(error_response(422, "error" => "proof did not match regex"))
      expect { client.submit("m_001", proof: "x", submitter_agent_id: "b") }
        .to raise_error(Oabp::UnprocessableEntityError, /did not match/)
    end

    it "requires proof and submitter" do
      expect { client.submit("m_001", proof: "", submitter_agent_id: "b") }
        .to raise_error(Oabp::ValidationError, /proof/)
      expect { client.submit("m_001", proof: "x") }
        .to raise_error(Oabp::ValidationError, /submitter_agent_id/)
    end
  end

  describe "#stats" do
    it "GETs /api/stats" do
      stub_request(:get, "#{base_url}/api/stats")
        .to_return(json("resolved" => 12, "open" => 3, "lifetime_reward_aigen_paid" => 108_000))
      stats = client.stats
      expect(stats.resolved).to eq(12)
      expect(stats.total).to eq(15)
      expect(stats.lifetime_reward_aigen_paid).to eq(108_000)
    end
  end

  describe "#reputation" do
    it "uses the dedicated endpoint when present" do
      stub_request(:get, "#{base_url}/api/agents/did%3Aagent%3Aalice/reputation")
        .to_return(json("agent_id" => "did:agent:alice", "aigen_balance" => 5000,
                        "missions_won" => 4))
      rep = client.reputation("did:agent:alice")
      expect(rep.aigen_balance).to eq(5000)
      expect(rep.missions_won).to eq(4)
    end

    it "derives reputation from missions when the endpoint 404s" do
      stub_request(:get, "#{base_url}/api/agents/did%3Aagent%3Abob/reputation")
        .to_return(status: 404, body: "not found")
      stub_request(:get, "#{base_url}/api/missions").to_return(json([
                                                                      sample_mission("id" => "m1", "creator_agent_id" => "did:agent:bob"),
                                                                      sample_mission(
                                                                        "id" => "m2",
                                                                        "submissions" => [{ "submitter_agent_id" => "did:agent:bob", "proof" => "x" }],
                                                                        "resolution" => { "winner_agent_id" => "did:agent:bob", "reward_paid" => 250 }
                                                                      )
                                                                    ]))

      rep = client.reputation("did:agent:bob")

      expect(rep.missions_created).to eq(1)
      expect(rep.missions_won).to eq(1)
      expect(rep.submissions_made).to eq(1)
      expect(rep.aigen_balance).to eq(250.0)
    end

    it "requires an agent id" do
      expect { client.reputation }.to raise_error(Oabp::ValidationError, /agent_id/)
    end
  end

  describe "A2A JSON-RPC" do
    it "POSTs /api/a2a with a JSON-RPC 2.0 envelope" do
      stub = stub_request(:post, "#{base_url}/api/a2a")
             .with(body: hash_including("jsonrpc" => "2.0", "method" => "tasks/list"))
             .to_return(json("jsonrpc" => "2.0", "id" => "1", "result" => { "tasks" => [] }))

      result = client.a2a("tasks/list", {}, id: "1")

      expect(stub).to have_been_requested
      expect(result).to be_a(Oabp::Models::A2AResult)
      expect(result.result).to eq("tasks" => [])
      expect(result).not_to be_error
    end

    it "raises an ApiError when the JSON-RPC response carries an error" do
      stub_request(:post, "#{base_url}/api/a2a")
        .to_return(json("jsonrpc" => "2.0", "id" => "1",
                        "error" => { "code" => -32_601, "message" => "method not found" }))
      expect { client.a2a("bogus/method") }
        .to raise_error(Oabp::ApiError, /method not found/)
    end

    it "builds a message/send envelope via #send_message" do
      stub = stub_request(:post, "#{base_url}/api/a2a")
             .with(body: hash_including(
               "method" => "message/send",
               "params" => hash_including(
                 "message" => hash_including(
                   "role" => "user",
                   "parts" => [hash_including("kind" => "text", "text" => "hello agent")]
                 )
               )
             ))
             .to_return(json("result" => { "ok" => true }))

      client.send_message("hello agent")
      expect(stub).to have_been_requested
    end

    it "fetches a task via #get_task" do
      stub = stub_request(:post, "#{base_url}/api/a2a")
             .with(body: hash_including("method" => "tasks/get",
                                        "params" => { "id" => "task_42" }))
             .to_return(json("result" => { "id" => "task_42", "status" => "completed" }))

      result = client.get_task("task_42")
      expect(stub).to have_been_requested
      expect(result.result["status"]).to eq("completed")
    end
  end

  describe "well-known documents" do
    it "fetches the ES256-signed agent card" do
      stub_request(:get, "#{base_url}/.well-known/agent-card.json")
        .to_return(json("name" => "AIGEN", "url" => "#{base_url}/api/a2a"))
      expect(client.agent_card["name"]).to eq("AIGEN")
    end

    it "fetches the JWKS" do
      stub_request(:get, "#{base_url}/.well-known/jwks.json")
        .to_return(json("keys" => [{ "kty" => "EC", "crv" => "P-256" }]))
      expect(client.jwks["keys"].first["crv"]).to eq("P-256")
    end
  end

  describe "error and transport handling" do
    it "maps 401 to AuthenticationError" do
      stub_request(:get, "#{base_url}/api/stats").to_return(error_response(401))
      expect { client.stats }.to raise_error(Oabp::AuthenticationError) do |e|
        expect(e.status).to eq(401)
        expect(e.path).to eq("/api/stats")
      end
    end

    it "maps 429 to RateLimitError" do
      stub_request(:get, "#{base_url}/api/stats").to_return(error_response(429))
      expect { client.stats }.to raise_error(Oabp::RateLimitError)
    end

    it "maps 5xx to ServerError" do
      stub_request(:get, "#{base_url}/api/stats").to_return(error_response(503))
      expect { client.stats }.to raise_error(Oabp::ServerError)
    end

    it "wraps a timeout in ConnectionError" do
      stub_request(:get, "#{base_url}/api/stats").to_timeout
      expect { client.stats }.to raise_error(Oabp::ConnectionError, /timed out|transport|connect/)
    end

    it "tolerates a non-JSON error body" do
      stub_request(:get, "#{base_url}/api/stats")
        .to_return(status: 500, body: "<html>oops</html>")
      expect { client.stats }.to raise_error(Oabp::ServerError)
    end

    it "sends the Authorization header when a token is configured" do
      stub = stub_request(:get, "#{base_url}/api/stats")
             .with(headers: { "Authorization" => "Bearer secret-token" })
             .to_return(json("resolved" => 0, "open" => 0, "lifetime_reward_aigen_paid" => 0))
      client(api_token: "secret-token").stats
      expect(stub).to have_been_requested
    end
  end
end
