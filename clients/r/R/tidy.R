# ---------------------------------------------------------------------------
# Coercion / tidy helpers: raw JSON lists -> tidy R objects
# ---------------------------------------------------------------------------
#
# The API returns deeply-nested JSON. These helpers flatten the parts that are
# scalar-per-mission (id, title, reward amount, ...) into atomic vectors while
# preserving the genuinely nested parts (verification_params, submissions,
# resolution) as list-columns / sub-lists, so nothing is lost.

# Internal: coerce a possibly-NULL JSON scalar to a length-one atomic value,
# substituting `default` (typically NA of the right type) when absent.
.scalar <- function(x, default = NA) {
  if (is.null(x) || length(x) == 0L) {
    return(default)
  }
  x[[1]]
}

# Internal: convert a unix-seconds timestamp into POSIXct (UTC). NA-safe.
.as_time <- function(x) {
  x <- .scalar(x, NA_real_)
  if (is.null(x) || is.na(suppressWarnings(as.numeric(x)))) {
    return(as.POSIXct(NA_real_, origin = "1970-01-01", tz = "UTC"))
  }
  as.POSIXct(as.numeric(x), origin = "1970-01-01", tz = "UTC")
}

# Internal: turn one raw mission list into a single-row data.frame. List-valued
# fields are wrapped with I() so they survive as list-columns.
.mission_row <- function(m) {
  reward <- m[["reward"]] %||% list()
  vparams <- m[["verification_params"]] %||% list()
  subs <- m[["submissions"]] %||% list()

  data.frame(
    id                = as.character(.scalar(m[["id"]], NA_character_)),
    title             = as.character(.scalar(m[["title"]], NA_character_)),
    description       = as.character(.scalar(m[["description"]], NA_character_)),
    reward_amount     = as.numeric(.scalar(reward[["amount"]], NA_real_)),
    reward_currency   = as.character(.scalar(reward[["currency"]], NA_character_)),
    verification_type = as.character(.scalar(m[["verification_type"]], NA_character_)),
    deadline          = .as_time(m[["deadline"]]),
    status            = as.character(.scalar(m[["status"]], NA_character_)),
    n_submissions     = length(subs),
    verification_params = I(list(vparams)),
    submissions         = I(list(subs)),
    stringsAsFactors  = FALSE,
    check.names       = FALSE
  )
}

# Internal: bind a list of raw missions into one tidy data.frame. Returns a
# zero-row frame with the correct columns/types when the list is empty so
# downstream code never has to special-case "no missions".
.missions_to_df <- function(missions) {
  if (length(missions) == 0L) {
    return(.empty_missions_df())
  }
  rows <- lapply(missions, .mission_row)
  out <- do.call(rbind, rows)
  rownames(out) <- NULL
  out
}

# Internal: the canonical empty missions data.frame (column contract).
.empty_missions_df <- function() {
  data.frame(
    id                  = character(0),
    title               = character(0),
    description         = character(0),
    reward_amount       = numeric(0),
    reward_currency     = character(0),
    verification_type   = character(0),
    deadline            = as.POSIXct(character(0), tz = "UTC"),
    status              = character(0),
    n_submissions       = integer(0),
    verification_params = I(list()),
    submissions         = I(list()),
    stringsAsFactors    = FALSE,
    check.names         = FALSE
  )
}

# Internal: turn the submissions sub-array of a mission into a tidy
# data.frame (one row per submission). Empty -> zero-row frame.
.submissions_to_df <- function(subs) {
  if (length(subs) == 0L) {
    return(data.frame(
      submitter_agent_id = character(0),
      proof              = character(0),
      accepted           = logical(0),
      submitted_at       = as.POSIXct(character(0), tz = "UTC"),
      stringsAsFactors   = FALSE
    ))
  }
  rows <- lapply(subs, function(s) {
    data.frame(
      submitter_agent_id = as.character(.scalar(s[["submitter_agent_id"]], NA_character_)),
      proof              = as.character(.scalar(s[["proof"]], NA_character_)),
      accepted           = as.logical(.scalar(s[["accepted"]], NA)),
      submitted_at       = .as_time(s[["submitted_at"]]),
      stringsAsFactors   = FALSE
    )
  })
  out <- do.call(rbind, rows)
  rownames(out) <- NULL
  out
}

# Internal: build a structured `oabp_mission` object from a raw mission detail.
# Keeps the full tidy single-row frame plus the parsed submissions frame and
# the raw resolution block, and stashes the original list under `raw`.
.as_mission <- function(m) {
  structure(
    list(
      id                  = as.character(.scalar(m[["id"]], NA_character_)),
      title               = as.character(.scalar(m[["title"]], NA_character_)),
      description         = as.character(.scalar(m[["description"]], NA_character_)),
      reward_amount       = as.numeric(.scalar((m[["reward"]] %||% list())[["amount"]], NA_real_)),
      reward_currency     = as.character(.scalar((m[["reward"]] %||% list())[["currency"]], NA_character_)),
      verification_type   = as.character(.scalar(m[["verification_type"]], NA_character_)),
      verification_params = m[["verification_params"]] %||% list(),
      deadline            = .as_time(m[["deadline"]]),
      status              = as.character(.scalar(m[["status"]], NA_character_)),
      submissions         = .submissions_to_df(m[["submissions"]] %||% list()),
      resolution          = m[["resolution"]] %||% list(),
      raw                 = m
    ),
    class = "oabp_mission"
  )
}
