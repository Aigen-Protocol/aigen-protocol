package oabp

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

// fakeServer is an in-memory implementation of the documented OABP / AIGEN API,
// just complete enough to assert the SDK speaks the wire protocol correctly.
type fakeServer struct {
	t          *testing.T
	deadline   int64 // unix seconds the create endpoint will echo back
	lastCreate CreateMissionRequest
	lastSubmit SubmitRequest
	lastA2A    rpcRequest
}

func newFakeServer(t *testing.T) (*fakeServer, *httptest.Server) {
	t.Helper()
	fs := &fakeServer{t: t, deadline: time.Now().Add(24 * time.Hour).Unix()}
	mux := http.NewServeMux()

	// GET /api/missions and POST /api/missions
	mux.HandleFunc("/api/missions", func(w http.ResponseWriter, r *http.Request) {
		switch r.Method {
		case http.MethodGet:
			writeJSON(w, http.StatusOK, fs.openMissions())
		case http.MethodPost:
			assertHeader(t, r, "Content-Type", "application/json")
			var req CreateMissionRequest
			decodeBody(t, r, &req)
			fs.lastCreate = req
			m := Mission{
				ID:                 "m-new",
				Title:              req.Title,
				Description:        req.Description,
				Reward:             Reward{Amount: req.RewardAmount, Currency: req.RewardCurrency},
				VerificationType:   req.VerificationType,
				VerificationParams: req.VerificationParams,
				Deadline:           NewUnixTime(time.Unix(fs.deadline, 0)),
				Status:             StatusOpen,
				CreatorAgent:       req.CreatorAgentID,
				Submissions:        []Submission{},
			}
			writeJSON(w, http.StatusCreated, m)
		default:
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		}
	})

	// GET /api/missions/{id}
	mux.HandleFunc("/api/missions/", func(w http.ResponseWriter, r *http.Request) {
		id := strings.TrimPrefix(r.URL.Path, "/api/missions/")
		if id == "m-1" {
			writeRaw(w, http.StatusOK, missionDetailJSON)
			return
		}
		writeJSON(w, http.StatusNotFound, map[string]string{"error": "mission not found"})
	})

	// POST /missions/{id}/submit  (note: no /api prefix)
	mux.HandleFunc("/missions/", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost || !strings.HasSuffix(r.URL.Path, "/submit") {
			http.Error(w, "not found", http.StatusNotFound)
			return
		}
		var req SubmitRequest
		decodeBody(t, r, &req)
		fs.lastSubmit = req
		res := SubmitResult{
			Accepted: true,
			Submission: &Submission{
				ID:             "s-1",
				SubmitterAgent: req.SubmitterAgentID,
				Proof:          req.Proof,
			},
			Message: "queued for verification",
		}
		writeJSON(w, http.StatusOK, res)
	})

	// GET /api/stats
	mux.HandleFunc("/api/stats", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, Stats{
			Resolved:                12,
			Open:                    3,
			LifetimeRewardAIGENPaid: 108000,
		})
	})

	// GET /api/reputation/{agent}
	mux.HandleFunc("/api/reputation/", func(w http.ResponseWriter, r *http.Request) {
		agent := strings.TrimPrefix(r.URL.Path, "/api/reputation/")
		// Include an undocumented field to prove Extra capture works.
		writeRaw(w, http.StatusOK, []byte(`{
			"agent_id": "`+agent+`",
			"aigen_balance": 4200.5,
			"missions_won": 7,
			"streak_days": 9
		}`))
	})

	// POST /api/a2a  (JSON-RPC 2.0)
	mux.HandleFunc("/api/a2a", func(w http.ResponseWriter, r *http.Request) {
		var req rpcRequest
		decodeBody(t, r, &req)
		fs.lastA2A = req
		resp := map[string]any{"jsonrpc": "2.0", "id": req.ID}
		switch req.Method {
		case A2AMethodMessageSend:
			resp["result"] = map[string]any{"id": "task-1", "status": map[string]string{"state": "submitted"}}
		case A2AMethodTasksGet:
			resp["result"] = map[string]any{"id": "task-1", "status": map[string]string{"state": "completed"}}
		case A2AMethodTasksList:
			resp["result"] = []map[string]any{
				{"id": "task-1", "status": map[string]string{"state": "completed"}},
				{"id": "task-2", "status": map[string]string{"state": "working"}},
			}
		case "boom":
			resp["error"] = map[string]any{"code": -32601, "message": "method not found"}
		default:
			resp["error"] = map[string]any{"code": -32601, "message": "method not found"}
		}
		writeJSON(w, http.StatusOK, resp)
	})

	// well-known documents
	mux.HandleFunc("/.well-known/agent-card.json", func(w http.ResponseWriter, r *http.Request) {
		writeRaw(w, http.StatusOK, []byte(`{
			"name": "AIGEN OABP Agent",
			"description": "agent-bounty marketplace",
			"url": "https://cryptogenesis.duckdns.org/api/a2a",
			"version": "1.0.0",
			"protocolVersion": "0.3.0",
			"preferredTransport": "JSONRPC",
			"capabilities": {"streaming": false}
		}`))
	})
	mux.HandleFunc("/.well-known/jwks.json", func(w http.ResponseWriter, r *http.Request) {
		writeRaw(w, http.StatusOK, []byte(`{"keys":[{"kty":"EC","crv":"P-256","x":"abc","y":"def","kid":"k1","alg":"ES256"}]}`))
	})

	srv := httptest.NewServer(mux)
	t.Cleanup(srv.Close)
	return fs, srv
}

// openMissions returns a deterministic list using a unix-seconds deadline to
// exercise the UnixTime codec.
func (fs *fakeServer) openMissions() []Mission {
	return []Mission{
		{
			ID:               "m-1",
			Title:            "Safety review of token 0xabc",
			Description:      "GoPlus token-security review",
			Reward:           Reward{Amount: 250, Currency: CurrencyAIGEN},
			VerificationType: VerificationOracle,
			VerificationParams: VerificationParams{
				OracleDescription: "GoPlus safety review of 0xabc",
			},
			Deadline:    NewUnixTime(time.Unix(fs.deadline, 0)),
			Status:      StatusOpen,
			Submissions: []Submission{},
		},
		{
			ID:                 "m-2",
			Title:              "SHA-256 puzzle",
			Description:        "match the regex",
			Reward:             Reward{Amount: 1000, Currency: CurrencyUSDC},
			VerificationType:   VerificationFirstValidMatch,
			VerificationParams: VerificationParams{Regex: "^[a-f0-9]{64}$"},
			Deadline:           NewUnixTime(time.Unix(fs.deadline, 0)),
			Status:             StatusOpen,
			Submissions:        []Submission{},
		},
	}
}

// missionDetailJSON is a hand-written detail payload (unix-seconds deadline,
// inline submissions, resolution, and an undocumented submission field) used to
// assert decoding against the literal wire format rather than a round-trip.
var missionDetailJSON = []byte(`{
  "id": "m-1",
  "title": "Safety review of token 0xabc",
  "description": "GoPlus token-security review",
  "reward": {"amount": 250, "currency": "AIGEN"},
  "verification_type": "oracle",
  "verification_params": {"oracle_description": "GoPlus safety review of 0xabc"},
  "deadline": 1893456000,
  "status": "resolved",
  "creator_agent_id": "agent.bob",
  "submissions": [
    {"id": "s-9", "submitter_agent_id": "agent.alice", "proof": "0xabc", "verified": true, "created_at": 1700000000, "score": 0.98}
  ],
  "resolution": {
    "status": "resolved",
    "winner_agent_id": "agent.alice",
    "reward_paid": 248.75,
    "currency": "AIGEN",
    "protocol_fee": 1.25,
    "resolved_at": 1700000500
  }
}`)

// --- helpers ---

func writeJSON(w http.ResponseWriter, code int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(v)
}

func writeRaw(w http.ResponseWriter, code int, b []byte) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	_, _ = w.Write(b)
}

func decodeBody(t *testing.T, r *http.Request, v any) {
	t.Helper()
	b, err := io.ReadAll(r.Body)
	if err != nil {
		t.Fatalf("read body: %v", err)
	}
	if err := json.Unmarshal(b, v); err != nil {
		t.Fatalf("decode body %q: %v", string(b), err)
	}
}

func assertHeader(t *testing.T, r *http.Request, key, want string) {
	t.Helper()
	if got := r.Header.Get(key); got != want {
		t.Errorf("header %s = %q, want %q", key, got, want)
	}
}

func testClient(t *testing.T, srv *httptest.Server, opts ...Option) *Client {
	t.Helper()
	all := append([]Option{WithBaseURL(srv.URL), WithHTTPClient(srv.Client())}, opts...)
	return New(all...)
}

// --- tests ---

func TestListMissions(t *testing.T) {
	_, srv := newFakeServer(t)
	c := testClient(t, srv)

	missions, err := c.ListMissions(context.Background())
	if err != nil {
		t.Fatalf("ListMissions: %v", err)
	}
	if len(missions) != 2 {
		t.Fatalf("got %d missions, want 2", len(missions))
	}
	if missions[0].ID != "m-1" || missions[0].VerificationType != VerificationOracle {
		t.Errorf("mission[0] = %+v", missions[0])
	}
	if missions[1].Reward.Currency != CurrencyUSDC || missions[1].Reward.Amount != 1000 {
		t.Errorf("mission[1] reward = %+v", missions[1].Reward)
	}
	if missions[0].Deadline.Unix() == 0 {
		t.Error("deadline did not decode from unix seconds")
	}
}

func TestGetMission(t *testing.T) {
	_, srv := newFakeServer(t)
	c := testClient(t, srv)

	m, err := c.GetMission(context.Background(), "m-1")
	if err != nil {
		t.Fatalf("GetMission: %v", err)
	}
	if m.Status != StatusResolved {
		t.Errorf("status = %q, want resolved", m.Status)
	}
	// Unix deadline 1893456000 -> 2030-01-01T00:00:00Z
	if got := m.Deadline.Time().Format(time.RFC3339); got != "2030-01-01T00:00:00Z" {
		t.Errorf("deadline = %s, want 2030-01-01T00:00:00Z", got)
	}
	if len(m.Submissions) != 1 || m.Submissions[0].SubmitterAgent != "agent.alice" {
		t.Fatalf("submissions = %+v", m.Submissions)
	}
	if m.Submissions[0].Verified == nil || !*m.Submissions[0].Verified {
		t.Error("submission.verified should decode to true")
	}
	// Undocumented "score" field must survive in Extra.
	if !strings.Contains(string(m.Submissions[0].Extra), `"score"`) {
		t.Errorf("Extra did not retain unknown field: %s", m.Submissions[0].Extra)
	}
	if m.Resolution == nil {
		t.Fatal("resolution should be present")
	}
	if m.Resolution.WinnerAgent != "agent.alice" || m.Resolution.ProtocolFee != 1.25 {
		t.Errorf("resolution = %+v", m.Resolution)
	}
	if m.Resolution.RewardPaid != 248.75 {
		t.Errorf("reward_paid = %v, want 248.75 (250 minus 0.5%% fee)", m.Resolution.RewardPaid)
	}
}

func TestGetMissionNotFound(t *testing.T) {
	_, srv := newFakeServer(t)
	c := testClient(t, srv)

	_, err := c.GetMission(context.Background(), "does-not-exist")
	if err == nil {
		t.Fatal("expected error for missing mission")
	}
	if !IsNotFound(err) {
		t.Fatalf("IsNotFound=false for %v", err)
	}
	ae, ok := err.(*APIError)
	if !ok || ae.StatusCode != http.StatusNotFound {
		t.Fatalf("error = %#v, want *APIError 404", err)
	}
	if ae.Message != "mission not found" {
		t.Errorf("message = %q, want decoded JSON error", ae.Message)
	}
}

func TestCreateMission(t *testing.T) {
	fs, srv := newFakeServer(t)
	c := testClient(t, srv, WithAgentID("agent.creator"))

	m, err := c.CreateMission(context.Background(), CreateMissionRequest{
		Title:            "Repo deliverable: Go SDK",
		Description:      "ship a working SDK",
		RewardAmount:     500,
		RewardCurrency:   CurrencyAIGEN,
		VerificationType: VerificationOracle,
		VerificationParams: VerificationParams{
			OracleDescription: "GitHub repo deliverable",
		},
		DeadlineHours: 48,
		// CreatorAgentID intentionally left blank: should default from WithAgentID.
	})
	if err != nil {
		t.Fatalf("CreateMission: %v", err)
	}
	if m.ID != "m-new" {
		t.Errorf("id = %q", m.ID)
	}
	// Server saw the defaulted agent id and the exact field names.
	if fs.lastCreate.CreatorAgentID != "agent.creator" {
		t.Errorf("server creator_agent_id = %q, want agent.creator", fs.lastCreate.CreatorAgentID)
	}
	if fs.lastCreate.DeadlineHours != 48 || fs.lastCreate.RewardCurrency != CurrencyAIGEN {
		t.Errorf("server saw %+v", fs.lastCreate)
	}
	if fs.lastCreate.VerificationParams.OracleDescription != "GitHub repo deliverable" {
		t.Errorf("oracle_description not transmitted: %+v", fs.lastCreate.VerificationParams)
	}
}

func TestCreateMissionValidation(t *testing.T) {
	c := New() // no network calls should happen
	ctx := context.Background()

	cases := map[string]CreateMissionRequest{
		"missing creator": {Title: "x", RewardAmount: 1, RewardCurrency: CurrencyAIGEN, VerificationType: VerificationOracle, DeadlineHours: 1},
		"missing title":   {CreatorAgentID: "a", RewardAmount: 1, RewardCurrency: CurrencyAIGEN, VerificationType: VerificationOracle, DeadlineHours: 1},
		"bad reward":      {CreatorAgentID: "a", Title: "x", RewardAmount: 0, RewardCurrency: CurrencyAIGEN, VerificationType: VerificationOracle, DeadlineHours: 1},
		"missing curr":    {CreatorAgentID: "a", Title: "x", RewardAmount: 1, VerificationType: VerificationOracle, DeadlineHours: 1},
		"bad deadline":    {CreatorAgentID: "a", Title: "x", RewardAmount: 1, RewardCurrency: CurrencyAIGEN, VerificationType: VerificationOracle, DeadlineHours: 0},
		"regex required":  {CreatorAgentID: "a", Title: "x", RewardAmount: 1, RewardCurrency: CurrencyAIGEN, VerificationType: VerificationFirstValidMatch, DeadlineHours: 1},
	}
	for name, req := range cases {
		t.Run(name, func(t *testing.T) {
			if _, err := c.CreateMission(ctx, req); err == nil {
				t.Errorf("expected validation error for %q", name)
			}
		})
	}
}

func TestSubmit(t *testing.T) {
	fs, srv := newFakeServer(t)
	c := testClient(t, srv, WithAgentID("agent.alice"))

	res, err := c.Submit(context.Background(), "m-2", SubmitRequest{
		Proof: "deadbeef",
	})
	if err != nil {
		t.Fatalf("Submit: %v", err)
	}
	if !res.Accepted {
		t.Error("expected accepted=true")
	}
	if res.Submission == nil || res.Submission.Proof != "deadbeef" {
		t.Errorf("submission = %+v", res.Submission)
	}
	if fs.lastSubmit.SubmitterAgentID != "agent.alice" {
		t.Errorf("submitter defaulted wrong: %q", fs.lastSubmit.SubmitterAgentID)
	}
	if fs.lastSubmit.Proof != "deadbeef" {
		t.Errorf("proof = %q", fs.lastSubmit.Proof)
	}
}

func TestSubmitRequiresProofAndAgent(t *testing.T) {
	_, srv := newFakeServer(t)
	cNoAgent := testClient(t, srv)
	if _, err := cNoAgent.Submit(context.Background(), "m-2", SubmitRequest{Proof: "x"}); err == nil {
		t.Error("expected error: no submitter agent id")
	}
	c := testClient(t, srv, WithAgentID("a"))
	if _, err := c.Submit(context.Background(), "m-2", SubmitRequest{}); err == nil {
		t.Error("expected error: empty proof")
	}
	if _, err := c.Submit(context.Background(), "", SubmitRequest{Proof: "x"}); err == nil {
		t.Error("expected error: empty mission id")
	}
}

func TestStats(t *testing.T) {
	_, srv := newFakeServer(t)
	c := testClient(t, srv)

	s, err := c.Stats(context.Background())
	if err != nil {
		t.Fatalf("Stats: %v", err)
	}
	if s.Open != 3 || s.Resolved != 12 || s.LifetimeRewardAIGENPaid != 108000 {
		t.Errorf("stats = %+v", s)
	}
}

func TestReputation(t *testing.T) {
	_, srv := newFakeServer(t)
	c := testClient(t, srv, WithAgentID("agent.alice"))

	// Empty arg -> defaults to WithAgentID.
	rep, err := c.Reputation(context.Background(), "")
	if err != nil {
		t.Fatalf("Reputation: %v", err)
	}
	if rep.AgentID != "agent.alice" {
		t.Errorf("agent_id = %q", rep.AgentID)
	}
	if rep.AIGENBalance != 4200.5 || rep.MissionsWon != 7 {
		t.Errorf("rep = %+v", rep)
	}
	// Undocumented field retained.
	if !strings.Contains(string(rep.Extra), `"streak_days"`) {
		t.Errorf("Extra lost unknown field: %s", rep.Extra)
	}

	if _, err := New().Reputation(context.Background(), ""); err == nil {
		t.Error("expected error when no agent id available")
	}
}

func TestA2ASendMessage(t *testing.T) {
	fs, srv := newFakeServer(t)
	c := testClient(t, srv)

	raw, err := c.SendMessage(context.Background(), TextMessage("hello agent"))
	if err != nil {
		t.Fatalf("SendMessage: %v", err)
	}
	if fs.lastA2A.JSONRPC != "2.0" || fs.lastA2A.Method != A2AMethodMessageSend {
		t.Errorf("server saw rpc = %+v", fs.lastA2A)
	}
	var task A2ATask
	if err := json.Unmarshal(raw, &task); err != nil {
		t.Fatalf("decode result: %v", err)
	}
	if task.ID != "task-1" {
		t.Errorf("task id = %q", task.ID)
	}
}

func TestA2AGetAndListTasks(t *testing.T) {
	_, srv := newFakeServer(t)
	c := testClient(t, srv)

	task, err := c.GetTask(context.Background(), "task-1")
	if err != nil {
		t.Fatalf("GetTask: %v", err)
	}
	if task.ID != "task-1" || len(task.Raw) == 0 {
		t.Errorf("task = %+v", task)
	}

	tasks, err := c.ListTasks(context.Background())
	if err != nil {
		t.Fatalf("ListTasks: %v", err)
	}
	if len(tasks) != 2 || tasks[1].ID != "task-2" {
		t.Errorf("tasks = %+v", tasks)
	}
}

func TestA2ARPCError(t *testing.T) {
	_, srv := newFakeServer(t)
	c := testClient(t, srv)

	err := c.A2ACall(context.Background(), "boom", map[string]any{}, nil)
	if err == nil {
		t.Fatal("expected rpc error")
	}
	re, ok := err.(*rpcError)
	if !ok {
		t.Fatalf("error type = %T, want *rpcError", err)
	}
	if re.Code != -32601 {
		t.Errorf("code = %d, want -32601", re.Code)
	}
}

func TestAgentCardAndJWKS(t *testing.T) {
	_, srv := newFakeServer(t)
	c := testClient(t, srv)

	card, err := c.AgentCard(context.Background())
	if err != nil {
		t.Fatalf("AgentCard: %v", err)
	}
	if card.Name != "AIGEN OABP Agent" || card.PreferredTransport != "JSONRPC" {
		t.Errorf("card = %+v", card)
	}
	// Raw retains the full signed document (incl. capabilities) for verification.
	if !strings.Contains(string(card.Raw), "capabilities") {
		t.Error("card.Raw should retain the full document")
	}

	keys, err := c.JWKS(context.Background())
	if err != nil {
		t.Fatalf("JWKS: %v", err)
	}
	if len(keys) != 1 || !strings.Contains(string(keys[0]), `"ES256"`) {
		t.Errorf("jwks = %v", keys)
	}
}

func TestContextCancellation(t *testing.T) {
	// A server that blocks until the request context is cancelled.
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		<-r.Context().Done()
	}))
	t.Cleanup(srv.Close)
	c := testClient(t, srv)

	ctx, cancel := context.WithTimeout(context.Background(), 50*time.Millisecond)
	defer cancel()
	_, err := c.ListMissions(ctx)
	if err == nil {
		t.Fatal("expected context deadline error")
	}
	if !strings.Contains(err.Error(), "context deadline exceeded") {
		t.Errorf("error = %v, want context deadline exceeded", err)
	}
}

func TestAPIErrorOnServerError(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		writeRaw(w, http.StatusInternalServerError, []byte(`{"error":"boom"}`))
	}))
	t.Cleanup(srv.Close)
	c := testClient(t, srv)

	_, err := c.Stats(context.Background())
	if err == nil {
		t.Fatal("expected error")
	}
	ae, ok := err.(*APIError)
	if !ok {
		t.Fatalf("error type = %T", err)
	}
	if ae.StatusCode != 500 || ae.Message != "boom" {
		t.Errorf("apierror = %+v", ae)
	}
	if !strings.Contains(ae.Error(), "boom") {
		t.Errorf("Error() = %q", ae.Error())
	}
}

func TestUnixTimeCodec(t *testing.T) {
	cases := []struct {
		in   string
		want int64
		zero bool
	}{
		{`1700000000`, 1700000000, false},
		{`"1700000000"`, 1700000000, false},
		{`1700000000.5`, 1700000000, false}, // fraction preserved as nsec, Unix()==whole
		{`null`, 0, true},                   // null -> Go zero time
		{`0`, 0, false},                     // epoch (1970) is a real time, not "unset"
	}
	for _, tc := range cases {
		var ut UnixTime
		if err := json.Unmarshal([]byte(tc.in), &ut); err != nil {
			t.Errorf("Unmarshal(%s): %v", tc.in, err)
			continue
		}
		if ut.IsZero() != tc.zero {
			t.Errorf("IsZero(%s) = %v, want %v", tc.in, ut.IsZero(), tc.zero)
		}
		if !tc.zero && ut.Unix() != tc.want {
			t.Errorf("Unix(%s) = %d, want %d", tc.in, ut.Unix(), tc.want)
		}
	}

	// Round trip through marshal.
	ut := NewUnixTime(time.Unix(1893456000, 0))
	b, err := json.Marshal(ut)
	if err != nil {
		t.Fatalf("Marshal: %v", err)
	}
	if string(b) != "1893456000" {
		t.Errorf("Marshal = %s, want 1893456000", b)
	}
}

func TestMissionExpired(t *testing.T) {
	past := Mission{Deadline: NewUnixTime(time.Now().Add(-time.Hour))}
	future := Mission{Deadline: NewUnixTime(time.Now().Add(time.Hour))}
	zero := Mission{}
	if !past.Expired() {
		t.Error("past mission should be expired")
	}
	if future.Expired() {
		t.Error("future mission should not be expired")
	}
	if zero.Expired() {
		t.Error("zero-deadline mission should not report expired")
	}
}

func TestWithOptions(t *testing.T) {
	c := New(
		WithBaseURL("https://example.test/"),
		WithAgentID("agent.x"),
		WithUserAgent("custom/1"),
		WithAPIKey("secret"),
	)
	if c.BaseURL() != "https://example.test" {
		t.Errorf("BaseURL = %q (trailing slash should be trimmed)", c.BaseURL())
	}
	if c.AgentID() != "agent.x" {
		t.Errorf("AgentID = %q", c.AgentID())
	}
	if c.userAgent != "custom/1" || c.apiKey != "secret" {
		t.Errorf("options not applied: ua=%q key=%q", c.userAgent, c.apiKey)
	}
}

func TestAPIKeyHeaderSent(t *testing.T) {
	var gotAuth string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotAuth = r.Header.Get("Authorization")
		writeJSON(w, http.StatusOK, []Mission{})
	}))
	t.Cleanup(srv.Close)
	c := testClient(t, srv, WithAPIKey("tok123"))
	if _, err := c.ListMissions(context.Background()); err != nil {
		t.Fatalf("ListMissions: %v", err)
	}
	if gotAuth != "Bearer tok123" {
		t.Errorf("Authorization = %q, want Bearer tok123", gotAuth)
	}
}
