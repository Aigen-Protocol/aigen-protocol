defmodule OABP.Fixtures do
  @moduledoc false
  # Realistic JSON fixtures mirroring the live OABP / AIGEN API payloads,
  # including the field aliases the production endpoints actually emit
  # (`reward_aigen`, `submission_count`, the `{count, missions}` envelope).

  def missions_list_envelope do
    %{
      "count" => 2,
      "missions" => [
        %{
          "id" => "m-001",
          "title" => "Safety-review a Base token",
          "description" => "Run a token-security safety review and report findings.",
          "reward_aigen" => 250,
          "verification_type" => "oracle",
          "verification_params" => %{
            "oracle_description" => "GoPlus token-security safety review"
          },
          "deadline" => 1_900_000_000,
          "status" => "open",
          "creator_agent_id" => "creator-1",
          "submission_count" => 1
        },
        %{
          "id" => "m-002",
          "title" => "Ship a Go SDK (repo deliverable)",
          "description" => "Deliver a GitHub repo with a working Go client.",
          "reward" => %{"amount" => 50, "currency" => "USDC"},
          "verification_type" => "first_valid_match",
          "verification_params" => %{"regex" => "https://github.com/.+"},
          "deadline" => 1_900_500_000,
          "status" => "open",
          "creator_agent_id" => "creator-2",
          "submission_count" => 0
        }
      ]
    }
  end

  def mission_detail do
    %{
      "id" => "m-001",
      "title" => "Safety-review a Base token",
      "description" => "Run a token-security safety review and report findings.",
      "reward" => %{"amount" => 250, "currency" => "AIGEN"},
      "verification_type" => "oracle",
      "verification_params" => %{"oracle_description" => "GoPlus token-security safety review"},
      "deadline" => 1_900_000_000,
      "status" => "open",
      "creator_agent_id" => "creator-1",
      "submissions" => [
        %{
          "id" => "s-1",
          "submitter_agent_id" => "agent-7",
          "proof" => "Token 0xabc... is safe: not a honeypot, ownership renounced.",
          "status" => "pending",
          "submitted_at" => 1_899_000_000
        }
      ],
      "resolution" => %{
        "passed" => true,
        "reason" => "valid: GoPlus reports no critical risks",
        "winner_agent_id" => "agent-7",
        "winning_submission_id" => "s-1",
        "reward_paid" => 250,
        "resolved_at" => 1_899_500_000
      }
    }
  end

  def created_mission do
    %{
      "id" => "m-new",
      "title" => "New mission",
      "description" => "freshly created",
      "reward" => %{"amount" => 100, "currency" => "AIGEN"},
      "verification_type" => "creator_judges",
      "verification_params" => %{},
      "deadline" => 1_901_000_000,
      "status" => "open",
      "creator_agent_id" => "my-agent",
      "submissions" => []
    }
  end

  def submit_ack do
    %{"ok" => true, "submission_id" => "s-42", "status" => "accepted"}
  end

  def stats do
    %{"resolved" => 17, "open" => 5, "lifetime_reward_aigen_paid" => 108_000}
  end

  # A2A message/send result: an agent Message with a text part + a data part
  # carrying the embedded mission feed (mirrors the live a2a server).
  def a2a_message_result do
    %{
      "kind" => "message",
      "role" => "agent",
      "messageId" => "msg-deadbeef",
      "contextId" => "ctx-1",
      "parts" => [
        %{"kind" => "text", "text" => "2 open mission(s) on the AIGEN OABP:\n• [m-001] ..."},
        %{
          "kind" => "data",
          "data" => %{"count" => 2, "missions" => [%{"id" => "m-001"}, %{"id" => "m-002"}]}
        }
      ]
    }
  end

  def a2a_rpc_error do
    %{
      "code" => -32001,
      "message" => "Task not found: this agent returns terminal messages, no persistent tasks"
    }
  end
end
