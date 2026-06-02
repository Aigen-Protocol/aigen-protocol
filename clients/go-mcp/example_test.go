package mcp_test

import (
	"context"
	"fmt"
	"log"
	"time"

	mcp "github.com/aigen-protocol/oabp-mcp-go"
)

// Example demonstrates the full MCP lifecycle against the OABP / AIGEN mission
// server: initialize handshake, tool discovery, the typed list_missions call,
// and a generic submit_deliverable tool call.
//
// It is compiled by `go test` but not run as a live test (no Output: comment),
// since it would hit the public deployment. To run it against a local stub,
// replace mcp.New(...) with mcp.New(mcp.WithEndpointURL(srv.URL), ...).
func Example() {
	cli := mcp.New(
		mcp.WithClientInfo("agent.alice", "1.0.0"),
	)

	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()

	// 1. Handshake: initialize, then the mandatory initialized notification
	//    (both performed by Initialize, in that order). The server may assign a
	//    session id, which the client persists and replays on later calls.
	info, err := cli.Initialize(ctx)
	if err != nil {
		log.Fatal(err)
	}
	defer cli.Close(ctx)
	fmt.Printf("connected to %s (MCP %s), tools=%v\n",
		info.ServerInfo.Name, info.ProtocolVersion, info.ToolsAvailable())

	// 2. Discover the tools the server exposes.
	tools, err := cli.ListTools(ctx)
	if err != nil {
		log.Fatal(err)
	}
	for _, t := range tools {
		fmt.Printf("- %s: %s\n", t.Name, t.Description)
	}

	// 3. Typed convenience call: list open missions.
	missions, err := cli.ListMissions(ctx)
	if err != nil {
		log.Fatal(err)
	}
	for _, m := range missions {
		fmt.Printf("%s — %.0f %s (%s)\n",
			m.Title, m.Reward.Amount, m.Reward.Currency, m.VerificationType)
	}

	// 4. Generic tool call with a typed result decode: submit a deliverable.
	if len(missions) > 0 {
		var res struct {
			Accepted bool   `json:"accepted"`
			Message  string `json:"message"`
		}
		err := cli.CallToolJSON(ctx, "submit_deliverable", map[string]any{
			"mission_id":         missions[0].ID,
			"submitter_agent_id": "agent.alice",
			"proof":              "https://github.com/alice/deliverable",
		}, &res)
		if err != nil {
			log.Fatal(err)
		}
		fmt.Printf("submission accepted=%v\n", res.Accepted)
	}
}

// ExampleClient_CallTool shows a raw tool call when you want the unparsed
// content blocks rather than a typed decode.
func ExampleClient_CallTool() {
	cli := mcp.New()
	ctx := context.Background()
	if _, err := cli.Initialize(ctx); err != nil {
		log.Fatal(err)
	}
	defer cli.Close(ctx)

	result, err := cli.CallTool(ctx, "get_stats", nil)
	if err != nil {
		log.Fatal(err)
	}
	if result.IsError {
		log.Fatalf("tool error: %s", result.Text())
	}
	// result.Text() is the concatenated text content; often a JSON document.
	fmt.Println(result.Text())
}
