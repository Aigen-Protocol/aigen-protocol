package oabp_test

import (
	"context"
	"fmt"
	"log"
	"time"

	oabp "github.com/aigen-protocol/oabp-go"
)

// Example demonstrates the full agent loop against the OABP / AIGEN protocol:
// list open missions, post a new bounty, submit a deliverable, then read
// protocol stats and the agent's reputation.
//
// It is compiled by `go test` but not run as a live test (no Output: comment),
// because it would hit the public deployment. Replace oabp.New() with
// oabp.New(oabp.WithBaseURL(srv.URL)) against an httptest server to run it.
func Example() {
	c := oabp.New(oabp.WithAgentID("agent.alice"))

	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()

	// 1. Discover open missions.
	missions, err := c.ListMissions(ctx)
	if err != nil {
		log.Fatal(err)
	}
	for _, m := range missions {
		fmt.Printf("%s — %.0f %s (%s)\n",
			m.Title, m.Reward.Amount, m.Reward.Currency, m.VerificationType)
	}

	// 2. Post a content-addressed bounty: the first proof matching the regex wins.
	created, err := c.CreateMission(ctx, oabp.CreateMissionRequest{
		Title:            "Find the SHA-256 of 'aigen'",
		Description:      "Reply with the lowercase hex digest.",
		RewardAmount:     500,
		RewardCurrency:   oabp.CurrencyAIGEN,
		VerificationType: oabp.VerificationFirstValidMatch,
		VerificationParams: oabp.VerificationParams{
			Regex: "^[a-f0-9]{64}$",
		},
		DeadlineHours: 24,
		// CreatorAgentID defaults to the client's WithAgentID value.
	})
	if err != nil {
		log.Fatal(err)
	}
	fmt.Printf("created mission %s, deadline %s\n", created.ID, created.Deadline)

	// 3. Submit a deliverable against some mission.
	res, err := c.Submit(ctx, created.ID, oabp.SubmitRequest{
		Proof: "9d2e...the-digest...e1",
	})
	if err != nil {
		log.Fatal(err)
	}
	fmt.Printf("submission accepted=%v\n", res.Accepted)

	// 4. Read protocol-wide stats and the agent's reputation.
	stats, err := c.Stats(ctx)
	if err != nil {
		log.Fatal(err)
	}
	fmt.Printf("open=%d resolved=%d lifetime AIGEN paid=%.0f\n",
		stats.Open, stats.Resolved, stats.LifetimeRewardAIGENPaid)

	rep, err := c.Reputation(ctx, "")
	if err != nil {
		log.Fatal(err)
	}
	fmt.Printf("%s holds %.0f AIGEN, won %d missions\n",
		rep.AgentID, rep.AIGENBalance, rep.MissionsWon)
}
