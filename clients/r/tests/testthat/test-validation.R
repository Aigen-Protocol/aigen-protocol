# Pure input-validation tests: arguments are checked before any request is
# built, so these need no mocking at all.

test_that("oabp_get_mission() rejects a bad id", {
  expect_error(oabp_get_mission(), "non-empty mission id")
  expect_error(oabp_get_mission(""), "non-empty mission id")
  expect_error(oabp_get_mission(c("a", "b")), "non-empty mission id")
  expect_error(oabp_get_mission(42), "non-empty mission id")
})

test_that("oabp_create_mission() validates required fields", {
  expect_error(
    oabp_create_mission("", "t", "d", 10),
    "creator_agent_id"
  )
  expect_error(
    oabp_create_mission("a", "t", "d", reward_amount = -1),
    "positive number"
  )
  expect_error(
    oabp_create_mission("a", "t", "d", reward_amount = 10, reward_currency = "BTC"),
    "should be one of"
  )
  expect_error(
    oabp_create_mission("a", "t", "d", reward_amount = 10,
                        verification_type = "magic"),
    "should be one of"
  )
  expect_error(
    oabp_create_mission("a", "t", "d", reward_amount = 10,
                        verification_params = "not-a-list"),
    "named list"
  )
  expect_error(
    oabp_create_mission("a", "t", "d", reward_amount = 10, deadline_hours = 0),
    "positive number"
  )
})

test_that("oabp_submit() validates its arguments", {
  expect_error(oabp_submit(id = "", "agent", "proof"), "`id`")
  expect_error(oabp_submit("m", "", "proof"), "submitter_agent_id")
  expect_error(oabp_submit("m", "agent", ""), "non-empty string")
})

test_that("oabp_a2a_request() validates method and params", {
  expect_error(oabp_a2a_request(method = 1), "`method`")
  expect_error(oabp_a2a_request("tasks/list", params = "x"), "named list")
})

test_that(".as_json_object() makes empty lists render as objects", {
  empty <- oabp:::.as_json_object(list())
  expect_length(empty, 0L)
  expect_equal(jsonlite::toJSON(empty, auto_unbox = TRUE), structure("{}", class = "json"))

  nonempty <- oabp:::.as_json_object(list(a = 1))
  expect_equal(
    jsonlite::toJSON(nonempty, auto_unbox = TRUE),
    structure('{"a":1}', class = "json")
  )
})

test_that("oabp_as_json() serialises lists and OABP objects", {
  j <- oabp_as_json(list(creator_agent_id = "agent_alice", reward_amount = 100),
                    pretty = FALSE)
  expect_type(j, "character")
  expect_match(j, '"creator_agent_id":"agent_alice"')
  expect_match(j, '"reward_amount":100')

  # an oabp_mission serialises its raw payload
  m <- oabp:::.as_mission(list(id = "m1", reward = list(amount = 5, currency = "USDC")))
  expect_match(oabp_as_json(m, pretty = FALSE), '"id":"m1"')
})

test_that(".as_time() is NA-safe and UTC", {
  t <- oabp:::.as_time(1900000000)
  expect_s3_class(t, "POSIXct")
  expect_equal(attr(t, "tzone"), "UTC")
  expect_true(is.na(oabp:::.as_time(NULL)))
  expect_true(is.na(oabp:::.as_time(list())))
})
