test_that("oabp_base_url() falls back to the public default", {
  withr::with_envvar(c(OABP_BASE_URL = NA), {
    expect_equal(oabp_base_url(), "https://cryptogenesis.duckdns.org")
  })
})

test_that("oabp_base_url() honours the OABP_BASE_URL env var", {
  withr::with_envvar(c(OABP_BASE_URL = "http://127.0.0.1:4025"), {
    expect_equal(oabp_base_url(), "http://127.0.0.1:4025")
  })
})

test_that("an explicit url argument wins over the env var", {
  withr::with_envvar(c(OABP_BASE_URL = "http://127.0.0.1:4025"), {
    expect_equal(oabp_base_url("https://node.example.com"), "https://node.example.com")
  })
})

test_that("trailing slashes are stripped", {
  expect_equal(oabp_base_url("https://node.example.com/"), "https://node.example.com")
  expect_equal(oabp_base_url("https://node.example.com///"), "https://node.example.com")
})

test_that("a non-scalar base url is rejected", {
  expect_error(oabp_base_url(c("a", "b")), "single string")
})
