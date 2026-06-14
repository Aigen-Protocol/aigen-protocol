# Response-parsing tests against on-disk fixtures (httptest2::with_mock_api()).
# All requests here are GET with no query string, so the fixture file paths are
# deterministic (no digest-hashed suffix). The base URL is the mocked host.

library(httptest2)

with_mock_api({

  test_that("oabp_list_missions() returns a tidy data.frame", {
    missions <- oabp_list_missions()

    expect_s3_class(missions, "data.frame")
    expect_equal(nrow(missions), 3L)
    expect_setequal(
      names(missions),
      c("id", "title", "description", "reward_amount", "reward_currency",
        "verification_type", "deadline", "status", "n_submissions",
        "verification_params", "submissions")
    )

    # scalar columns are flattened to atomic vectors
    expect_type(missions$id, "character")
    expect_type(missions$reward_amount, "double")
    expect_s3_class(missions$deadline, "POSIXct")
    expect_identical(missions$id, c("mission_alpha", "mission_beta", "mission_gamma"))
    expect_identical(missions$reward_currency, c("AIGEN", "USDC", "AIGEN"))

    # n_submissions is computed from the (preserved) list-column
    expect_identical(missions$n_submissions, c(0L, 1L, 1L))
  })

  test_that("nested fields survive as list-columns", {
    missions <- oabp_list_missions()
    expect_true(is.list(missions$verification_params))
    expect_equal(missions$verification_params[[1]]$regex, "FLAG\\{[a-f0-9]{8}\\}")
    expect_equal(
      missions$verification_params[[2]]$oracle_description,
      "github repo deliverable, language=Rust"
    )
    # submissions list-column carries the raw per-mission submissions
    expect_length(missions$submissions[[1]], 0L)
    expect_equal(missions$submissions[[2]][[1]]$submitter_agent_id, "agent_bob")
  })

  test_that("client-side currency filter works", {
    usdc <- oabp_list_missions(currency = "USDC")
    expect_equal(nrow(usdc), 1L)
    expect_equal(usdc$id, "mission_beta")

    aigen <- oabp_list_missions(currency = "AIGEN")
    expect_equal(nrow(aigen), 2L)
    expect_setequal(aigen$id, c("mission_alpha", "mission_gamma"))
  })

  test_that("oabp_get_mission() returns a structured oabp_mission", {
    m <- oabp_get_mission("mission_alpha")

    expect_s3_class(m, "oabp_mission")
    expect_equal(m$id, "mission_alpha")
    expect_equal(m$reward_amount, 100)
    expect_equal(m$reward_currency, "AIGEN")
    expect_equal(m$verification_type, "first_valid_match")
    expect_s3_class(m$deadline, "POSIXct")

    # submissions tidied to a data.frame
    expect_s3_class(m$submissions, "data.frame")
    expect_equal(nrow(m$submissions), 2L)
    expect_identical(m$submissions$accepted, c(TRUE, FALSE))
    expect_equal(m$submissions$submitter_agent_id[1], "agent_dan")

    # resolution preserved
    expect_equal(m$resolution$winner_agent_id, "agent_dan")
    expect_equal(m$resolution$reward_paid, 99.5)
    expect_equal(m$resolution$fee, 0.5)
  })

  test_that("oabp_mission prints a readable summary", {
    m <- oabp_get_mission("mission_alpha")
    out <- format(m)
    expect_match(out, "oabp_mission")
    expect_match(out, "mission_alpha")
    expect_match(out, "100 AIGEN")
    expect_match(out, "winner")
    # print returns its argument invisibly
    expect_output(res <- print(m))
    expect_identical(res, m)
  })

  test_that("oabp_stats() parses headline numbers", {
    s <- oabp_stats()
    expect_s3_class(s, "oabp_stats")
    expect_equal(s$open, 12L)
    expect_equal(s$resolved, 137L)
    expect_equal(s$lifetime_reward_aigen_paid, 108452.75)
    expect_output(print(s), "lifetime_reward_aigen_paid")
  })

})

test_that("empty mission list yields a zero-row tidy frame", {
  # No HTTP needed: exercise the tidy-er directly on an empty array.
  df <- oabp:::.missions_to_df(list())
  expect_s3_class(df, "data.frame")
  expect_equal(nrow(df), 0L)
  expect_true("reward_amount" %in% names(df))
  expect_type(df$reward_amount, "double")
})
