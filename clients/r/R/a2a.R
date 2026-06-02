# ---------------------------------------------------------------------------
# A2A (agent-to-agent) JSON-RPC + agent discovery
# ---------------------------------------------------------------------------
#
# The node exposes an A2A JSON-RPC 2.0 endpoint at POST /api/a2a with methods
# message/send, tasks/get and tasks/list, an ES256-signed agent card at
# /.well-known/agent-card.json and the verifying key set at
# /.well-known/jwks.json.

#' Fetch the signed agent card
#'
#' Calls `GET /.well-known/agent-card.json` and returns the agent card as a
#' parsed list. The card advertises the agent's identity, A2A endpoint and
#' skills and is signed with ES256 (the verifying key is published at
#' `/.well-known/jwks.json`). This client returns the card as served; it does
#' not verify the JWS signature.
#'
#' @param base_url OABP base URL. Defaults to [oabp_base_url()].
#'
#' @return A named list: the parsed agent card.
#' @export
#' @examples
#' \dontrun{
#' card <- oabp_agent_card()
#' card$name
#' card$url        # the A2A JSON-RPC endpoint
#' }
oabp_agent_card <- function(base_url = oabp_base_url()) {
  req <- .oabp_req(".well-known/agent-card.json", base_url = base_url)
  .oabp_perform(req)
}

#' Low-level A2A JSON-RPC call
#'
#' Performs a single JSON-RPC 2.0 request against `POST /api/a2a`. Most callers
#' will prefer the typed wrappers [oabp_a2a_message_send()],
#' [oabp_a2a_task_get()] and [oabp_a2a_tasks_list()].
#'
#' @param method JSON-RPC method name, e.g. `"message/send"`, `"tasks/get"`,
#'   `"tasks/list"`.
#' @param params Named list of method parameters (sent as the JSON-RPC
#'   `params` member). Defaults to an empty object.
#' @param id JSON-RPC request id. Defaults to a fresh value.
#' @param token Optional bearer token if the endpoint requires authentication.
#' @param base_url OABP base URL. Defaults to [oabp_base_url()].
#'
#' @return The JSON-RPC `result` member (parsed) on success. On a JSON-RPC
#'   `error` member, an R error is raised carrying the error `code` and
#'   `message`.
#' @export
#' @examples
#' \dontrun{
#' oabp_a2a_request("tasks/list")
#' }
oabp_a2a_request <- function(method, params = list(), id = NULL,
                             token = NULL, base_url = oabp_base_url()) {
  .check_string(method, "method")
  if (!is.list(params)) {
    stop("`params` must be a (possibly empty) named list.", call. = FALSE)
  }
  if (is.null(id)) {
    id <- as.character(as.integer(Sys.time()))
  }

  payload <- list(
    jsonrpc = "2.0",
    id      = id,
    method  = method,
    params  = .as_json_object(params)
  )

  req <- .oabp_req("api/a2a", base_url = base_url, token = token)
  req <- httr2::req_method(req, "POST")
  req <- httr2::req_body_json(req, payload, auto_unbox = TRUE)
  body <- .oabp_perform(req)

  if (!is.null(body[["error"]])) {
    err <- body[["error"]]
    code <- .scalar(err[["code"]], NA)
    msg  <- .scalar(err[["message"]], "unknown JSON-RPC error")
    stop(sprintf("A2A JSON-RPC error %s: %s", code, msg), call. = FALSE)
  }
  body[["result"]] %||% list()
}

#' Send a message to an agent over A2A
#'
#' Wraps the `message/send` JSON-RPC method. Builds a minimal A2A message
#' (one text part) and sends it to the node, returning the resulting task /
#' message object.
#'
#' @param text The message text.
#' @param role Message role, defaults to `"user"`.
#' @param task_id Optional existing task id to continue a conversation.
#' @param message_id Optional client-supplied message id. Defaults to a fresh
#'   value.
#' @param token Optional bearer token.
#' @param base_url OABP base URL. Defaults to [oabp_base_url()].
#'
#' @return The parsed JSON-RPC result (typically a task object).
#' @export
#' @examples
#' \dontrun{
#' task <- oabp_a2a_message_send("List the open USDC missions, please.")
#' task$id
#' }
oabp_a2a_message_send <- function(text, role = "user", task_id = NULL,
                                  message_id = NULL, token = NULL,
                                  base_url = oabp_base_url()) {
  .check_string(text, "text")
  if (is.null(message_id)) {
    message_id <- paste0("msg-", as.integer(Sys.time()))
  }
  message <- list(
    role      = role,
    parts     = list(list(kind = "text", text = text)),
    messageId = message_id,
    kind      = "message"
  )
  if (!is.null(task_id)) {
    message[["taskId"]] <- task_id
  }
  oabp_a2a_request("message/send", params = list(message = message),
                   token = token, base_url = base_url)
}

#' Fetch an A2A task by id
#'
#' Wraps the `tasks/get` JSON-RPC method.
#'
#' @param task_id Task id to fetch.
#' @param token Optional bearer token.
#' @param base_url OABP base URL. Defaults to [oabp_base_url()].
#'
#' @return The parsed task object.
#' @export
#' @examples
#' \dontrun{
#' oabp_a2a_task_get("task_123")
#' }
oabp_a2a_task_get <- function(task_id, token = NULL, base_url = oabp_base_url()) {
  .check_string(task_id, "task_id")
  oabp_a2a_request("tasks/get", params = list(id = task_id),
                   token = token, base_url = base_url)
}

#' List A2A tasks
#'
#' Wraps the `tasks/list` JSON-RPC method.
#'
#' @param token Optional bearer token.
#' @param base_url OABP base URL. Defaults to [oabp_base_url()].
#'
#' @return The parsed result of `tasks/list` (typically a list of task
#'   objects). Returned as-is from the node.
#' @export
#' @examples
#' \dontrun{
#' oabp_a2a_tasks_list()
#' }
oabp_a2a_tasks_list <- function(token = NULL, base_url = oabp_base_url()) {
  oabp_a2a_request("tasks/list", token = token, base_url = base_url)
}
