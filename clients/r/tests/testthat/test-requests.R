# Request-construction tests. without_internet() makes every request throw a
# condition whose message is "METHOD url body". httptest2's verb-expectations
# build the pattern paste0("METHOD ", url, " ", ...) and match it against that
# message (here as a regex, via fixed = FALSE).
#
# Helpers below keep the call sites readable:
#  * expect_route()    asserts only METHOD + URL (literal).
#  * expect_body()     asserts a JSON field appears anywhere in the body, by
#                      matching "<url> .*<field>" as a regex.

library(httptest2)

# Escape regex metacharacters in a literal fragment. The class lists ] and [
# first and omits -, so the character class itself is well formed.
.rx <- function(x) gsub("([][{}()*+?.^$|\\\\])", "\\\\\\1", x)

# Assert that a POST to `url` has `field` (a literal JSON fragment) somewhere
# in its body.
expect_body <- function(expr, url, field) {
  expect_POST(expr, .rx(url), paste0(".*", .rx(field)), fixed = FALSE)
}

test_that("oabp_list_missions() hits GET /api/missions", {
  without_internet({
    expect_GET(oabp_list_missions(),
               "https://cryptogenesis.duckdns.org/api/missions")
  })
})

test_that("status filter is sent as a query parameter", {
  without_internet({
    expect_GET(oabp_list_missions(status = "open"),
               .rx("https://cryptogenesis.duckdns.org/api/missions?status=open"),
               fixed = FALSE)
  })
})

test_that("oabp_get_mission() hits GET /api/missions/{id}", {
  without_internet({
    expect_GET(oabp_get_mission("mission_alpha"),
               "https://cryptogenesis.duckdns.org/api/missions/mission_alpha")
  })
})

test_that("oabp_create_mission() POSTs to the right URL", {
  without_internet({
    expect_POST(oabp_create_mission("agent_alice", "t", "d", reward_amount = 100),
                "https://cryptogenesis.duckdns.org/api/missions")
  })
})

test_that("oabp_create_mission() body carries the expected fields", {
  url <- "https://cryptogenesis.duckdns.org/api/missions"
  mk <- function() {
    oabp_create_mission(
      creator_agent_id    = "agent_alice",
      title               = "Find the magic phrase",
      description         = "Submit text containing the flag.",
      reward_amount       = 100,
      reward_currency     = "AIGEN",
      verification_type   = "first_valid_match",
      verification_params = list(regex = "abc"),
      deadline_hours      = 24
    )
  }
  without_internet({
    expect_body(mk(), url, '"creator_agent_id":"agent_alice"')
    expect_body(mk(), url, '"reward_amount":100')
    expect_body(mk(), url, '"reward_currency":"AIGEN"')
    expect_body(mk(), url, '"verification_type":"first_valid_match"')
    expect_body(mk(), url, '"regex":"abc"')
    expect_body(mk(), url, '"deadline_hours":24')
  })
})

test_that("empty verification_params serialises as a JSON object, not array", {
  url <- "https://cryptogenesis.duckdns.org/api/missions"
  without_internet({
    expect_body(
      oabp_create_mission(
        creator_agent_id  = "agent_alice",
        title             = "Open judging",
        description        = "Creator decides.",
        reward_amount      = 5,
        verification_type  = "creator_judges",
        deadline_hours     = 12
      ),
      url, '"verification_params":{}'
    )
  })
})

test_that("oabp_submit() POSTs to /missions/{id}/submit", {
  without_internet({
    expect_POST(
      oabp_submit("mission_beta", "agent_bob", "https://github.com/agent_bob/x"),
      "https://cryptogenesis.duckdns.org/missions/mission_beta/submit"
    )
  })
})

test_that("oabp_submit() body carries submitter and proof", {
  url <- "https://cryptogenesis.duckdns.org/missions/mission_beta/submit"
  sub <- function() oabp_submit("mission_beta", "agent_bob", "PROOF-XYZ")
  without_internet({
    expect_body(sub(), url, '"submitter_agent_id":"agent_bob"')
    expect_body(sub(), url, '"proof":"PROOF-XYZ"')
  })
})

test_that("A2A message/send POSTs a JSON-RPC envelope to /api/a2a", {
  url <- "https://cryptogenesis.duckdns.org/api/a2a"
  snd <- function() oabp_a2a_message_send("hello there")
  without_internet({
    expect_POST(snd(), url)
    expect_body(snd(), url, '"jsonrpc":"2.0"')
    expect_body(snd(), url, '"method":"message/send"')
    expect_body(snd(), url, '"text":"hello there"')
  })
})

test_that("A2A tasks/get POSTs the right method and params", {
  url <- "https://cryptogenesis.duckdns.org/api/a2a"
  g <- function() oabp_a2a_task_get("task_123")
  without_internet({
    expect_body(g(), url, '"method":"tasks/get"')
    expect_body(g(), url, '"id":"task_123"')
  })
})

test_that("A2A tasks/list POSTs the right method", {
  url <- "https://cryptogenesis.duckdns.org/api/a2a"
  without_internet({
    expect_body(oabp_a2a_tasks_list(), url, '"method":"tasks/list"')
  })
})

test_that("oabp_agent_card() hits GET /.well-known/agent-card.json", {
  without_internet({
    expect_GET(oabp_agent_card(),
               "https://cryptogenesis.duckdns.org/.well-known/agent-card.json")
  })
})

test_that("oabp_stats() hits GET /api/stats", {
  without_internet({
    expect_GET(oabp_stats(),
               "https://cryptogenesis.duckdns.org/api/stats")
  })
})

test_that("the base URL is configurable per call", {
  without_internet({
    expect_GET(oabp_list_missions(base_url = "https://node.example.com"),
               "https://node.example.com/api/missions")
  })
})
