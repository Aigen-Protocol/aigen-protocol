defmodule OABP.ModelsTest do
  use ExUnit.Case, async: true

  alias OABP.{Mission, Message, Part, Resolution, Reward, Stats, Submission}

  describe "Reward.from_json/2" do
    test "nested object" do
      assert Reward.from_json(%{"amount" => 100, "currency" => "USDC"}, %{}) ==
               %Reward{amount: 100, currency: "USDC"}
    end

    test "bare number is treated as AIGEN" do
      assert Reward.from_json(7, %{}) == %Reward{amount: 7, currency: "AIGEN"}
    end

    test "falls back to the flat reward_aigen field on the parent" do
      assert Reward.from_json(nil, %{"reward_aigen" => 42}) ==
               %Reward{amount: 42, currency: "AIGEN"}
    end

    test "parses numeric strings" do
      assert Reward.from_json(%{"amount" => "12.5", "currency" => "AIGEN"}, %{}).amount == 12.5
    end
  end

  describe "Mission.from_json/1" do
    test "builds submissions and resolution from nested data" do
      mission =
        Mission.from_json(%{
          "id" => 123,
          "title" => "t",
          "reward" => %{"amount" => 5, "currency" => "AIGEN"},
          "verification_type" => "oracle",
          "deadline" => 1_900_000_000,
          "submissions" => [%{"id" => "s1", "proof" => "p"}],
          "resolution" => %{"passed" => false, "reason" => "empty repo"}
        })

      assert mission.id == "123"
      assert [%Submission{id: "s1", proof: "p"}] = mission.submissions
      assert mission.submission_count == 1
      assert %Resolution{passed: false, reason: "empty repo"} = mission.resolution
    end

    test "no resolution -> nil" do
      assert Mission.from_json(%{"id" => "x"}).resolution == nil
    end

    test "keeps the raw map for forward-compatibility" do
      raw = %{"id" => "x", "future_field" => 99}
      assert Mission.from_json(raw).raw == raw
    end
  end

  describe "Mission.list_from_json/1" do
    test "envelope, bare array, and garbage" do
      assert [%Mission{id: "a"}] = Mission.list_from_json(%{"missions" => [%{"id" => "a"}]})
      assert [%Mission{id: "b"}] = Mission.list_from_json([%{"id" => "b"}])
      assert [] == Mission.list_from_json(%{"unexpected" => true})
      assert [] == Mission.list_from_json(nil)
    end
  end

  describe "Mission helpers" do
    test "usdc?/1" do
      usdc = Mission.from_json(%{"reward" => %{"amount" => 1, "currency" => "usdc"}})
      aigen = Mission.from_json(%{"reward_aigen" => 1})
      assert Mission.usdc?(usdc)
      refute Mission.usdc?(aigen)
    end

    test "seconds_left/2" do
      m = Mission.from_json(%{"deadline" => 1_000})
      assert Mission.seconds_left(m, 600) == 400
      assert Mission.seconds_left(m, 1_500) == -500
      assert Mission.seconds_left(Mission.from_json(%{}), 0) == nil
    end
  end

  describe "Stats.from_json/1" do
    test "parses counters" do
      assert Stats.from_json(%{
               "resolved" => 1,
               "open" => 2,
               "lifetime_reward_aigen_paid" => 3.5
             }) == %Stats{
               resolved: 1,
               open: 2,
               lifetime_reward_aigen_paid: 3.5,
               raw: %{
                 "resolved" => 1,
                 "open" => 2,
                 "lifetime_reward_aigen_paid" => 3.5
               }
             }
    end
  end

  describe "A2A Message / Part" do
    test "Message.text/1 joins text parts, Message.data/1 returns first data part" do
      msg =
        Message.from_json(%{
          "kind" => "message",
          "role" => "agent",
          "messageId" => "m1",
          "parts" => [
            %{"kind" => "text", "text" => "hello"},
            %{"kind" => "text", "text" => "world"},
            %{"kind" => "data", "data" => %{"k" => "v"}}
          ]
        })

      assert msg.message_id == "m1"
      assert Message.text(msg) == "hello\nworld"
      assert Message.data(msg) == %{"k" => "v"}
    end

    test "Part builders and wire form" do
      assert Part.text("hi") == %Part{kind: "text", text: "hi"}
      assert Part.data(%{a: 1}) == %Part{kind: "data", data: %{a: 1}}
      assert Part.to_wire(Part.text("hi")) == %{"kind" => "text", "text" => "hi"}
      assert Part.to_wire(Part.data(%{a: 1})) == %{"kind" => "data", "data" => %{a: 1}}
    end
  end
end
