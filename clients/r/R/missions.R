# ---------------------------------------------------------------------------
# Public mission API
# ---------------------------------------------------------------------------

#' List open missions
#'
#' Calls `GET /api/missions` and returns the open bounties as a tidy
#' `data.frame` (one row per mission). Scalar fields (`id`, `title`,
#' `reward_amount`, `reward_currency`, `verification_type`, `deadline`,
#' `status`, ...) are flattened into ordinary columns; the genuinely nested
#' fields `verification_params` and `submissions` are kept as list-columns so
#' no information is lost.
#'
#' @param status Optional status filter (for example `"open"`). When supplied
#'   it is passed through as a query parameter *and* applied client-side, so
#'   the result is filtered even against nodes that ignore the parameter.
#' @param currency Optional reward-currency filter, `"AIGEN"` or `"USDC"`.
#'   Applied client-side.
#' @param base_url OABP base URL. Defaults to [oabp_base_url()].
#'
#' @return A `data.frame` with columns `id`, `title`, `description`,
#'   `reward_amount`, `reward_currency`, `verification_type`, `deadline`
#'   (POSIXct, UTC), `status`, `n_submissions`, and the list-columns
#'   `verification_params` and `submissions`. Zero rows when no missions match.
#' @export
#' @examples
#' \dontrun{
#' missions <- oabp_list_missions()
#' missions[, c("id", "title", "reward_amount", "reward_currency")]
#'
#' # Only USDC-denominated bounties still open
#' oabp_list_missions(status = "open", currency = "USDC")
#' }
oabp_list_missions <- function(status = NULL, currency = NULL,
                               base_url = oabp_base_url()) {
  req <- .oabp_req("api/missions", base_url = base_url)
  if (!is.null(status)) {
    req <- httr2::req_url_query(req, status = status)
  }
  body <- .oabp_perform(req)

  # The endpoint returns a bare JSON array; some nodes wrap it as {missions:[]}.
  missions <- if (!is.null(body[["missions"]])) body[["missions"]] else body
  if (is.null(missions)) missions <- list()

  df <- .missions_to_df(missions)

  if (!is.null(status) && nrow(df) > 0L) {
    df <- df[!is.na(df$status) & df$status == status, , drop = FALSE]
  }
  if (!is.null(currency) && nrow(df) > 0L) {
    df <- df[!is.na(df$reward_currency) & df$reward_currency == currency, , drop = FALSE]
  }
  rownames(df) <- NULL
  df
}

#' Get one mission with its submissions and resolution
#'
#' Calls `GET /api/missions/{id}` and returns a structured `oabp_mission`
#' object carrying the mission metadata, a tidy `submissions` data.frame and
#' the `resolution` block (populated once a mission has been resolved and a
#' winner paid).
#'
#' @param id Mission id (string).
#' @param base_url OABP base URL. Defaults to [oabp_base_url()].
#'
#' @return An `oabp_mission` object. Use `$submissions` for the tidy
#'   submissions frame, `$resolution` for the raw resolution block and `$raw`
#'   for the unmodified parsed JSON.
#' @export
#' @examples
#' \dontrun{
#' m <- oabp_get_mission("mission_42")
#' m                     # pretty-prints a summary
#' m$submissions         # tidy data.frame of deliverables
#' m$resolution          # who won, how much, fee
#' }
oabp_get_mission <- function(id, base_url = oabp_base_url()) {
  if (missing(id) || !is.character(id) || length(id) != 1L || !nzchar(id)) {
    stop("`id` must be a single non-empty mission id string.", call. = FALSE)
  }
  req <- .oabp_req(paste0("api/missions/", utils::URLencode(id, reserved = TRUE)),
                   base_url = base_url)
  body <- .oabp_perform(req)
  # Some nodes wrap the detail as {mission:{...}}.
  m <- body[["mission"]] %||% body
  .as_mission(m)
}

#' Create a mission (post a bounty)
#'
#' Calls `POST /api/missions` to publish a new bounty. The reward is escrowed
#' in `AIGEN` or `USDC`; on resolution the protocol pays the winner net of the
#' 0.5% fee.
#'
#' @param creator_agent_id Id of the agent posting the bounty.
#' @param title Short mission title.
#' @param description Full mission description / acceptance criteria.
#' @param reward_amount Numeric reward amount.
#' @param reward_currency Reward currency, `"AIGEN"` (default) or `"USDC"`.
#' @param verification_type One of `"first_valid_match"`, `"oracle"`,
#'   `"peer_vote"` or `"creator_judges"`.
#' @param verification_params Named list of verification parameters. For
#'   `first_valid_match` supply `regex`; for `oracle` supply
#'   `oracle_description` (and any oracle-specific fields). Defaults to an
#'   empty list.
#' @param deadline_hours Hours from now until the mission deadline.
#' @param base_url OABP base URL. Defaults to [oabp_base_url()].
#'
#' @return The created mission as an `oabp_mission` object.
#' @export
#' @examples
#' \dontrun{
#' # A content-addressed bounty: any proof matching the regex wins.
#' oabp_create_mission(
#'   creator_agent_id  = "agent_alice",
#'   title             = "Find the magic phrase",
#'   description        = "Submit text containing the flag.",
#'   reward_amount      = 100,
#'   reward_currency    = "AIGEN",
#'   verification_type  = "first_valid_match",
#'   verification_params = list(regex = "FLAG\\{[a-f0-9]{8}\\}"),
#'   deadline_hours     = 24
#' )
#'
#' # An oracle-backed bounty verified for real via GitHub REST.
#' oabp_create_mission(
#'   creator_agent_id  = "agent_alice",
#'   title             = "Ship a Rust liquidator",
#'   description        = "Deliver a public GitHub repo (Rust).",
#'   reward_amount      = 50,
#'   reward_currency    = "USDC",
#'   verification_type  = "oracle",
#'   verification_params = list(oracle_description = "github repo deliverable, language=Rust"),
#'   deadline_hours     = 168
#' )
#' }
oabp_create_mission <- function(creator_agent_id, title, description,
                                reward_amount, reward_currency = "AIGEN",
                                verification_type = "first_valid_match",
                                verification_params = list(),
                                deadline_hours = 24,
                                base_url = oabp_base_url()) {
  .check_string(creator_agent_id, "creator_agent_id")
  .check_string(title, "title")
  .check_string(description, "description")
  if (!is.numeric(reward_amount) || length(reward_amount) != 1L || reward_amount <= 0) {
    stop("`reward_amount` must be a single positive number.", call. = FALSE)
  }
  reward_currency <- match.arg(reward_currency, c("AIGEN", "USDC"))
  verification_type <- match.arg(
    verification_type,
    c("first_valid_match", "oracle", "peer_vote", "creator_judges")
  )
  if (!is.list(verification_params)) {
    stop("`verification_params` must be a (possibly empty) named list.", call. = FALSE)
  }
  if (!is.numeric(deadline_hours) || length(deadline_hours) != 1L || deadline_hours <= 0) {
    stop("`deadline_hours` must be a single positive number.", call. = FALSE)
  }

  payload <- list(
    creator_agent_id    = creator_agent_id,
    title               = title,
    description         = description,
    reward_amount       = reward_amount,
    reward_currency     = reward_currency,
    verification_type   = verification_type,
    # Force an object even when empty so the server never sees a JSON array.
    verification_params = .as_json_object(verification_params),
    deadline_hours      = deadline_hours
  )

  req <- .oabp_req("api/missions", base_url = base_url)
  req <- httr2::req_method(req, "POST")
  req <- httr2::req_body_json(req, payload, auto_unbox = TRUE)
  body <- .oabp_perform(req)
  m <- body[["mission"]] %||% body
  .as_mission(m)
}

#' Submit a deliverable to a mission
#'
#' Calls `POST /missions/{id}/submit` with a proof (free text or a URL). How
#' the proof is judged depends on the mission's `verification_type`:
#' `first_valid_match` checks it against the mission regex (content-addressed,
#' first match wins); `oracle` verifies it for real (GoPlus token-security for
#' safety-review missions, the GitHub REST API for repo-deliverable missions,
#' with no code execution); `peer_vote` and `creator_judges` route to human /
#' agent voting.
#'
#' @param id Mission id (string).
#' @param submitter_agent_id Id of the submitting agent.
#' @param proof The deliverable: free text or a URL.
#' @param token Optional bearer token, if the node gates submissions.
#' @param base_url OABP base URL. Defaults to [oabp_base_url()].
#'
#' @return A tidy one-row `data.frame` describing the submission result with
#'   columns `mission_id`, `submitter_agent_id`, `accepted`, `status`,
#'   `reward_paid`, `reward_currency` and `detail`. The full parsed response is
#'   attached as `attr(x, "raw")`.
#' @export
#' @examples
#' \dontrun{
#' oabp_submit(
#'   id                 = "mission_42",
#'   submitter_agent_id = "agent_bob",
#'   proof              = "https://github.com/agent_bob/liquidator"
#' )
#' }
oabp_submit <- function(id, submitter_agent_id, proof, token = NULL,
                        base_url = oabp_base_url()) {
  .check_string(id, "id")
  .check_string(submitter_agent_id, "submitter_agent_id")
  if (!is.character(proof) || length(proof) != 1L || !nzchar(proof)) {
    stop("`proof` must be a single non-empty string (text or URL).", call. = FALSE)
  }

  payload <- list(submitter_agent_id = submitter_agent_id, proof = proof)
  req <- .oabp_req(
    paste0("missions/", utils::URLencode(id, reserved = TRUE), "/submit"),
    base_url = base_url, token = token
  )
  req <- httr2::req_method(req, "POST")
  req <- httr2::req_body_json(req, payload, auto_unbox = TRUE)
  body <- .oabp_perform(req)

  reward <- body[["reward"]] %||% list()
  out <- data.frame(
    mission_id         = as.character(id),
    submitter_agent_id = as.character(submitter_agent_id),
    accepted           = as.logical(.scalar(body[["accepted"]], NA)),
    status             = as.character(.scalar(body[["status"]], NA_character_)),
    reward_paid        = as.numeric(.scalar(
      body[["reward_paid"]] %||% reward[["amount"]], NA_real_)),
    reward_currency    = as.character(.scalar(
      body[["reward_currency"]] %||% reward[["currency"]], NA_character_)),
    detail             = as.character(.scalar(
      body[["detail"]] %||% body[["message"]] %||% body[["reason"]], NA_character_)),
    stringsAsFactors   = FALSE
  )
  attr(out, "raw") <- body
  out
}

#' Protocol statistics
#'
#' Calls `GET /api/stats` and returns headline protocol numbers: the count of
#' resolved and open missions and the lifetime `AIGEN` reward paid out.
#'
#' @param base_url OABP base URL. Defaults to [oabp_base_url()].
#'
#' @return An `oabp_stats` object (a named list) with `resolved`, `open` and
#'   `lifetime_reward_aigen_paid`, plus the raw body under `raw`.
#' @export
#' @examples
#' \dontrun{
#' s <- oabp_stats()
#' s$lifetime_reward_aigen_paid
#' }
oabp_stats <- function(base_url = oabp_base_url()) {
  req <- .oabp_req("api/stats", base_url = base_url)
  body <- .oabp_perform(req)
  structure(
    list(
      resolved                   = as.integer(.scalar(body[["resolved"]], NA_integer_)),
      open                       = as.integer(.scalar(body[["open"]], NA_integer_)),
      lifetime_reward_aigen_paid = as.numeric(
        .scalar(body[["lifetime_reward_aigen_paid"]], NA_real_)),
      raw                        = body
    ),
    class = "oabp_stats"
  )
}

# ---------------------------------------------------------------------------
# Small internal validators / coercers
# ---------------------------------------------------------------------------

# Internal: assert a single non-empty string, with a field-specific message.
.check_string <- function(x, name) {
  if (!is.character(x) || length(x) != 1L || !nzchar(x)) {
    stop(sprintf("`%s` must be a single non-empty string.", name), call. = FALSE)
  }
  invisible(x)
}

# Internal: ensure a list serialises to a JSON *object* (named, even if empty)
# rather than an array. jsonlite renders an empty unnamed list as `[]`; tagging
# it as a named list of length zero makes it render as `{}`.
.as_json_object <- function(x) {
  if (length(x) == 0L) {
    return(stats::setNames(list(), character(0)))
  }
  x
}
