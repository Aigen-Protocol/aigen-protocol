defmodule OABPTest do
  use ExUnit.Case, async: true

  alias OABP.{Client, Error, Mission, Message, Reward, Stats}
  alias OABP.Fixtures

  setup do
    bypass = Bypass.open()

    client =
      Client.new(
        base_url: "http://localhost:#{bypass.port}",
        agent_id: "my-agent",
        adapter: OABP.HTTP.Httpc,
        timeout: 5_000
      )

    {:ok, bypass: bypass, client: client}
  end

  defp json(conn, status, term) do
    conn
    |> Plug.Conn.put_resp_header("content-type", "application/json")
    |> Plug.Conn.resp(status, Jason.encode!(term))
  end

  defp read_json_body(conn) do
    {:ok, raw, conn} = Plug.Conn.read_body(conn)
    {Jason.decode!(raw), conn}
  end

  # ---------------------------------------------------------------------------
  # list_missions/1
  # ---------------------------------------------------------------------------

  describe "list_missions/1" do
    test "parses the {count, missions} envelope into Mission structs", %{
      bypass: bypass,
      client: client
    } do
      Bypass.expect_once(bypass, "GET", "/api/missions", fn conn ->
        assert {"accept", "application/json"} in conn.req_headers
        json(conn, 200, Fixtures.missions_list_envelope())
      end)

      assert {:ok, [m1, m2]} = OABP.list_missions(client)

      assert %Mission{id: "m-001", title: "Safety-review a Base token"} = m1
      # reward_aigen alias -> AIGEN reward
      assert m1.reward == %Reward{amount: 250, currency: "AIGEN"}
      assert m1.verification_type == "oracle"
      assert m1.submission_count == 1
      assert m1.deadline == 1_900_000_000

      # nested reward object with USDC
      assert %Reward{amount: 50, currency: "USDC"} = m2.reward
      assert Mission.usdc?(m2)
      refute Mission.usdc?(m1)
    end

    test "also accepts a bare JSON array", %{bypass: bypass, client: client} do
      Bypass.expect_once(bypass, "GET", "/api/missions", fn conn ->
        json(conn, 200, [%{"id" => "x", "title" => "bare", "reward_aigen" => 1}])
      end)

      assert {:ok, [%Mission{id: "x", title: "bare"}]} = OABP.list_missions(client)
    end

    test "maps a non-2xx response to an :http error", %{bypass: bypass, client: client} do
      Bypass.expect_once(bypass, "GET", "/api/missions", fn conn ->
        json(conn, 503, %{"error" => "down"})
      end)

      assert {:error, %Error{kind: :http, status: 503, body: %{"error" => "down"}}} =
               OABP.list_missions(client)
    end

    test "maps a dropped connection to a :transport error", %{bypass: bypass, client: client} do
      Bypass.down(bypass)
      assert {:error, %Error{kind: :transport}} = OABP.list_missions(client)
      Bypass.up(bypass)
    end
  end

  # ---------------------------------------------------------------------------
  # get_mission/2
  # ---------------------------------------------------------------------------

  describe "get_mission/2" do
    test "returns a mission with submissions and resolution", %{bypass: bypass, client: client} do
      Bypass.expect_once(bypass, "GET", "/api/missions/m-001", fn conn ->
        json(conn, 200, Fixtures.mission_detail())
      end)

      assert {:ok, mission} = OABP.get_mission(client, "m-001")
      assert [submission] = mission.submissions
      assert submission.submitter_agent_id == "agent-7"
      assert submission.proof =~ "not a honeypot"

      assert mission.resolution.passed == true
      assert mission.resolution.winner_agent_id == "agent-7"
      assert mission.resolution.reward_paid == 250
    end

    test "url-encodes the mission id", %{bypass: bypass, client: client} do
      Bypass.expect_once(bypass, "GET", "/api/missions/weird%2Fid%20x", fn conn ->
        json(conn, 200, %{"id" => "weird/id x"})
      end)

      assert {:ok, %Mission{id: "weird/id x"}} = OABP.get_mission(client, "weird/id x")
    end

    test "rejects an empty id without a request", %{client: client} do
      assert {:error, %Error{kind: :invalid}} = OABP.get_mission(client, "")
    end

    test "surfaces a 404 as an :http error", %{bypass: bypass, client: client} do
      Bypass.expect_once(bypass, "GET", "/api/missions/nope", fn conn ->
        json(conn, 404, %{"error" => "not found"})
      end)

      assert {:error, %Error{kind: :http, status: 404}} = OABP.get_mission(client, "nope")
    end
  end

  # ---------------------------------------------------------------------------
  # create_mission/2
  # ---------------------------------------------------------------------------

  describe "create_mission/2" do
    test "POSTs the documented payload and parses the result", %{bypass: bypass, client: client} do
      Bypass.expect_once(bypass, "POST", "/api/missions", fn conn ->
        {body, conn} = read_json_body(conn)

        assert body == %{
                 "creator_agent_id" => "my-agent",
                 "title" => "New mission",
                 "description" => "do a thing",
                 "reward_amount" => 100,
                 "reward_currency" => "AIGEN",
                 "verification_type" => "creator_judges",
                 "verification_params" => %{},
                 "deadline_hours" => 48
               }

        json(conn, 201, Fixtures.created_mission())
      end)

      assert {:ok, %Mission{id: "m-new"}} =
               OABP.create_mission(client,
                 title: "New mission",
                 description: "do a thing",
                 reward_amount: 100,
                 verification_type: "creator_judges",
                 deadline_hours: 48
               )
    end

    test "honors an explicit creator_agent_id and verification_params", %{
      bypass: bypass,
      client: client
    } do
      Bypass.expect_once(bypass, "POST", "/api/missions", fn conn ->
        {body, conn} = read_json_body(conn)
        assert body["creator_agent_id"] == "other-agent"
        assert body["reward_currency"] == "USDC"
        assert body["verification_params"] == %{"regex" => "0x[a-f0-9]{40}"}
        assert body["deadline_hours"] == 24
        json(conn, 201, Fixtures.created_mission())
      end)

      assert {:ok, %Mission{}} =
               OABP.create_mission(client,
                 creator_agent_id: "other-agent",
                 title: "t",
                 description: "d",
                 reward_amount: 10,
                 reward_currency: "USDC",
                 verification_type: "first_valid_match",
                 verification_params: %{"regex" => "0x[a-f0-9]{40}"}
               )
    end

    test "returns :invalid when required options are missing (no request made)", %{client: client} do
      assert {:error, %Error{kind: :invalid, message: msg}} =
               OABP.create_mission(client, title: "t")

      assert msg =~ "description"
      assert msg =~ "reward_amount"
      assert msg =~ "verification_type"
    end
  end

  # ---------------------------------------------------------------------------
  # submit/4
  # ---------------------------------------------------------------------------

  describe "submit/4" do
    test "POSTs proof with the client's default agent id", %{bypass: bypass, client: client} do
      Bypass.expect_once(bypass, "POST", "/missions/m-001/submit", fn conn ->
        {body, conn} = read_json_body(conn)
        assert body == %{"submitter_agent_id" => "my-agent", "proof" => "https://github.com/me/x"}
        json(conn, 200, Fixtures.submit_ack())
      end)

      assert {:ok, %{"ok" => true, "submission_id" => "s-42"}} =
               OABP.submit(client, "m-001", "https://github.com/me/x")
    end

    test "lets the caller override the submitter agent id", %{bypass: bypass, client: client} do
      Bypass.expect_once(bypass, "POST", "/missions/m-001/submit", fn conn ->
        {body, conn} = read_json_body(conn)
        assert body["submitter_agent_id"] == "agent-9"
        json(conn, 200, Fixtures.submit_ack())
      end)

      assert {:ok, _} = OABP.submit(client, "m-001", "proof text", submitter_agent_id: "agent-9")
    end

    test "requires an agent id when the client has none", %{bypass: bypass} do
      anon =
        Client.new(
          base_url: "http://localhost:#{bypass.port}",
          adapter: OABP.HTTP.Httpc
        )

      assert {:error, %Error{kind: :invalid, message: msg}} = OABP.submit(anon, "m-001", "p")
      assert msg =~ "submitter_agent_id"
    end

    test "rejects empty mission_id / proof", %{client: client} do
      assert {:error, %Error{kind: :invalid}} = OABP.submit(client, "", "p")
      assert {:error, %Error{kind: :invalid}} = OABP.submit(client, "m", "")
    end
  end

  # ---------------------------------------------------------------------------
  # stats/1
  # ---------------------------------------------------------------------------

  test "stats/1 returns the ecosystem counters", %{bypass: bypass, client: client} do
    Bypass.expect_once(bypass, "GET", "/api/stats", fn conn ->
      json(conn, 200, Fixtures.stats())
    end)

    assert {:ok, %Stats{resolved: 17, open: 5, lifetime_reward_aigen_paid: 108_000}} =
             OABP.stats(client)
  end

  # ---------------------------------------------------------------------------
  # A2A
  # ---------------------------------------------------------------------------

  describe "a2a_send/3" do
    test "wraps the utterance in a JSON-RPC message/send and parses the agent Message", %{
      bypass: bypass,
      client: client
    } do
      Bypass.expect_once(bypass, "POST", "/api/a2a", fn conn ->
        {body, conn} = read_json_body(conn)
        assert body["jsonrpc"] == "2.0"
        assert body["method"] == "message/send"
        assert is_binary(body["id"])
        [part] = body["params"]["message"]["parts"]
        assert part == %{"kind" => "text", "text" => "list missions"}
        assert body["params"]["message"]["role"] == "user"

        json(conn, 200, %{
          "jsonrpc" => "2.0",
          "id" => body["id"],
          "result" => Fixtures.a2a_message_result()
        })
      end)

      assert {:ok, %Message{} = msg} = OABP.a2a_send(client, "list missions")
      assert msg.role == "agent"
      assert msg.context_id == "ctx-1"
      assert Message.text(msg) =~ "2 open mission(s)"
      assert %{"count" => 2, "missions" => [_, _]} = Message.data(msg)
    end

    test "passes a context id through", %{bypass: bypass, client: client} do
      Bypass.expect_once(bypass, "POST", "/api/a2a", fn conn ->
        {body, conn} = read_json_body(conn)
        assert body["params"]["message"]["contextId"] == "ctx-xyz"

        json(conn, 200, %{
          "jsonrpc" => "2.0",
          "id" => body["id"],
          "result" => Fixtures.a2a_message_result()
        })
      end)

      assert {:ok, %Message{}} = OABP.a2a_send(client, "hi", context_id: "ctx-xyz")
    end

    test "maps a JSON-RPC error object to an :rpc error", %{bypass: bypass, client: client} do
      Bypass.expect_once(bypass, "POST", "/api/a2a", fn conn ->
        {body, conn} = read_json_body(conn)

        json(conn, 200, %{
          "jsonrpc" => "2.0",
          "id" => body["id"],
          "error" => Fixtures.a2a_rpc_error()
        })
      end)

      assert {:error, %Error{kind: :rpc, status: -32001, message: msg}} =
               OABP.a2a_send(client, "anything")

      assert msg =~ "Task not found"
    end
  end

  test "a2a_task/3 issues a tasks/get call", %{bypass: bypass, client: client} do
    Bypass.expect_once(bypass, "POST", "/api/a2a", fn conn ->
      {body, conn} = read_json_body(conn)
      assert body["method"] == "tasks/get"
      assert body["params"] == %{"id" => "task-1"}

      json(conn, 200, %{
        "jsonrpc" => "2.0",
        "id" => body["id"],
        "result" => %{"status" => "completed"}
      })
    end)

    assert {:ok, %{"status" => "completed"}} = OABP.a2a_task(client, "task-1")
  end

  test "a2a_tasks/2 issues a tasks/list call", %{bypass: bypass, client: client} do
    Bypass.expect_once(bypass, "POST", "/api/a2a", fn conn ->
      {body, conn} = read_json_body(conn)
      assert body["method"] == "tasks/list"
      json(conn, 200, %{"jsonrpc" => "2.0", "id" => body["id"], "result" => []})
    end)

    assert {:ok, []} = OABP.a2a_tasks(client)
  end

  test "decodes an A2A response missing result/error as a :decode error", %{
    bypass: bypass,
    client: client
  } do
    Bypass.expect_once(bypass, "POST", "/api/a2a", fn conn ->
      json(conn, 200, %{"jsonrpc" => "2.0", "id" => "1"})
    end)

    assert {:error, %Error{kind: :decode}} = OABP.a2a_call(client, "message/send", %{})
  end

  # ---------------------------------------------------------------------------
  # discovery
  # ---------------------------------------------------------------------------

  test "agent_card/1 fetches the well-known card", %{bypass: bypass, client: client} do
    Bypass.expect_once(bypass, "GET", "/.well-known/agent-card.json", fn conn ->
      json(conn, 200, %{"name" => "AIGEN Protocol", "protocolVersion" => "0.3.0"})
    end)

    assert {:ok, %{"name" => "AIGEN Protocol"}} = OABP.agent_card(client)
  end

  test "jwks/1 fetches the well-known JWKS", %{bypass: bypass, client: client} do
    Bypass.expect_once(bypass, "GET", "/.well-known/jwks.json", fn conn ->
      json(conn, 200, %{"keys" => [%{"kty" => "EC", "crv" => "P-256"}]})
    end)

    assert {:ok, %{"keys" => [%{"kty" => "EC"}]}} = OABP.jwks(client)
  end

  # ---------------------------------------------------------------------------
  # malformed JSON
  # ---------------------------------------------------------------------------

  test "a 2xx body that is not JSON becomes a :decode error", %{bypass: bypass, client: client} do
    Bypass.expect_once(bypass, "GET", "/api/stats", fn conn ->
      conn
      |> Plug.Conn.put_resp_header("content-type", "application/json")
      |> Plug.Conn.resp(200, "<html>not json</html>")
    end)

    assert {:error, %Error{kind: :decode}} = OABP.stats(client)
  end
end
