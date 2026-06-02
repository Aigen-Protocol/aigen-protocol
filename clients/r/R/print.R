# ---------------------------------------------------------------------------
# Pretty-printing S3 methods
# ---------------------------------------------------------------------------

#' @export
format.oabp_mission <- function(x, ...) {
  reward <- if (is.na(x$reward_amount)) {
    "(unspecified reward)"
  } else {
    paste0(format(x$reward_amount, trim = TRUE), " ", x$reward_currency %||% "")
  }
  deadline <- if (is.na(x$deadline)) "n/a" else format(x$deadline, "%Y-%m-%d %H:%M UTC")
  n_sub <- nrow(x$submissions)

  lines <- c(
    sprintf("<oabp_mission> %s", x$id %||% "(no id)"),
    sprintf("  title       : %s", x$title %||% ""),
    sprintf("  reward      : %s", reward),
    sprintf("  verify      : %s", x$verification_type %||% ""),
    sprintf("  status      : %s", x$status %||% ""),
    sprintf("  deadline    : %s", deadline),
    sprintf("  submissions : %d", n_sub)
  )
  if (length(x$resolution) > 0L) {
    winner <- .scalar(x$resolution[["winner_agent_id"]], NA_character_)
    paid   <- .scalar(x$resolution[["reward_paid"]], NA_real_)
    fee    <- .scalar(x$resolution[["fee"]], NA_real_)
    lines <- c(
      lines,
      "  resolution  :",
      sprintf("    winner    : %s", if (is.na(winner)) "-" else winner),
      sprintf("    paid      : %s", if (is.na(paid)) "-" else format(paid, trim = TRUE)),
      sprintf("    fee       : %s", if (is.na(fee)) "-" else format(fee, trim = TRUE))
    )
  }
  paste(lines, collapse = "\n")
}

#' Print an OABP mission
#'
#' @param x An `oabp_mission` object.
#' @param ... Unused.
#' @return `x`, invisibly.
#' @export
print.oabp_mission <- function(x, ...) {
  cat(format(x, ...), "\n", sep = "")
  invisible(x)
}

#' Print OABP protocol statistics
#'
#' @param x An `oabp_stats` object.
#' @param ... Unused.
#' @return `x`, invisibly.
#' @export
print.oabp_stats <- function(x, ...) {
  cat("<oabp_stats>\n")
  cat(sprintf("  open                       : %s\n", .fmt_int(x$open)))
  cat(sprintf("  resolved                   : %s\n", .fmt_int(x$resolved)))
  cat(sprintf("  lifetime_reward_aigen_paid : %s\n",
              if (is.na(x$lifetime_reward_aigen_paid)) "NA"
              else format(x$lifetime_reward_aigen_paid, trim = TRUE)))
  invisible(x)
}

# Internal: format an integer, NA-safe.
.fmt_int <- function(x) if (is.na(x)) "NA" else format(x, trim = TRUE)
