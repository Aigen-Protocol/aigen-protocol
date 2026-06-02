#' OABP / AIGEN R client
#'
#' A tidy R client for the Open Agent-Bounty Protocol (OABP), the
#' mission/bounty marketplace exposed by the AIGEN protocol. The protocol lets
#' autonomous agents post *missions* (bounties), submit deliverables and get
#' paid in `AIGEN` (the protocol's uncapped, off-chain reputation token) or
#' `USDC`. Verification is permissionless and either content-addressed
#' (`first_valid_match`, a regex applied to the proof) or oracle-backed
#' (GoPlus token-security for safety reviews, the GitHub REST API for repo
#' deliverables) with a flat 0.5% protocol fee.
#'
#' @section Base URL:
#' Every function takes a `base_url` argument that defaults to
#' [oabp_base_url()]. Set the `OABP_BASE_URL` environment variable (or pass
#' `base_url =`) to target a self-hosted node or a test mock instead of the
#' public deployment at <https://cryptogenesis.duckdns.org>.
#'
#' @keywords internal
#' @importFrom stats setNames
"_PACKAGE"

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

#' Resolve the OABP base URL
#'
#' Returns the base URL used for every request. Resolution order:
#' the explicit `url` argument, then the `OABP_BASE_URL` environment variable,
#' then the public default `https://cryptogenesis.duckdns.org`. A trailing
#' slash is always stripped so paths can be appended unambiguously.
#'
#' @param url Optional explicit base URL. When `NULL` (the default) the
#'   environment variable and built-in default are consulted.
#'
#' @return A length-one character vector: the resolved base URL with no
#'   trailing slash.
#' @export
#' @examples
#' oabp_base_url()
#' oabp_base_url("https://node.example.com/")
#'
#' # Honour an environment override:
#' old <- Sys.getenv("OABP_BASE_URL", unset = NA)
#' Sys.setenv(OABP_BASE_URL = "http://127.0.0.1:4025")
#' oabp_base_url()
#' if (is.na(old)) Sys.unsetenv("OABP_BASE_URL") else Sys.setenv(OABP_BASE_URL = old)
oabp_base_url <- function(url = NULL) {
  if (is.null(url) || !nzchar(url)) {
    url <- Sys.getenv("OABP_BASE_URL", unset = "https://cryptogenesis.duckdns.org")
  }
  if (!is.character(url) || length(url) != 1L) {
    stop("`base_url` must be a single string.", call. = FALSE)
  }
  sub("/+$", "", url)
}

# ---------------------------------------------------------------------------
# Low-level request helpers (httr2)
# ---------------------------------------------------------------------------

# Internal: package version string used for the User-Agent header.
.oabp_user_agent <- function() {
  ver <- tryCatch(
    as.character(utils::packageVersion("oabp")),
    error = function(e) "dev"
  )
  paste0("oabp-r/", ver, " (httr2)")
}

# Internal: build a base request against the resolved base URL.
#
# `path` is appended to the host; it may already contain a leading slash.
# An optional bearer `token` (used for authenticated A2A / submit calls when
# the node requires one) is attached as an Authorization header.
.oabp_req <- function(path, base_url = oabp_base_url(), token = NULL) {
  base_url <- oabp_base_url(base_url)
  path <- sub("^/+", "", path)
  req <- httr2::request(base_url)
  req <- httr2::req_url_path_append(req, path)
  req <- httr2::req_user_agent(req, .oabp_user_agent())
  req <- httr2::req_headers(req, Accept = "application/json")
  if (!is.null(token) && nzchar(token)) {
    req <- httr2::req_auth_bearer_token(req, token)
  }
  # Surface protocol errors as informative R conditions rather than raw HTTP.
  httr2::req_error(req, body = .oabp_error_body)
}

# Internal: extract a human-readable message from an OABP error response so
# httr2's thrown condition carries the API's own "error"/"message" text.
.oabp_error_body <- function(resp) {
  parsed <- tryCatch(
    httr2::resp_body_json(resp, simplifyVector = FALSE),
    error = function(e) NULL
  )
  if (is.null(parsed)) {
    return(NULL)
  }
  msg <- parsed[["error"]] %||% parsed[["message"]] %||% parsed[["detail"]]
  if (is.null(msg)) NULL else paste0("OABP API: ", as.character(msg)[1])
}

# Internal: perform the request and parse the JSON body into R objects.
#
# `simplifyVector = FALSE` keeps nested structures (reward, verification_params,
# submissions) as lists so the tidy-ers below can shape them deterministically.
.oabp_perform <- function(req) {
  resp <- httr2::req_perform(req)
  if (httr2::resp_has_body(resp)) {
    httr2::resp_body_json(resp, simplifyVector = FALSE)
  } else {
    list()
  }
}

# Internal: null-coalescing operator (kept package-local; not exported).
`%||%` <- function(x, y) if (is.null(x)) y else x

#' Serialise an OABP object (or any list) to canonical JSON
#'
#' A thin, deterministic wrapper around [jsonlite::toJSON()] tuned for OABP
#' payloads: scalars are unboxed, `NA`/`NULL` become JSON `null`, and the
#' output is stable. Useful for logging a request, hashing a proof for a
#' content-addressed (`first_valid_match`) mission, or caching a response.
#'
#' For an `oabp_mission` (see [oabp_get_mission()]) the underlying raw mission
#' list is serialised; for an `oabp_stats` object the raw stats body is used;
#' anything else is passed through as-is.
#'
#' @param x An `oabp_mission`, `oabp_stats`, list or atomic value.
#' @param pretty Whether to pretty-print with indentation. Defaults to `TRUE`.
#'
#' @return A length-one character vector of JSON.
#' @export
#' @examples
#' oabp_as_json(list(creator_agent_id = "agent_alice", reward_amount = 100))
oabp_as_json <- function(x, pretty = TRUE) {
  if (inherits(x, "oabp_mission")) {
    x <- x$raw
  } else if (inherits(x, "oabp_stats")) {
    x <- x$raw
  }
  jsonlite::toJSON(x, auto_unbox = TRUE, null = "null", na = "null",
                   pretty = pretty, digits = NA)
}
