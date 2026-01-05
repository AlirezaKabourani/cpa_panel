#!/usr/bin/env Rscript

# CPA_Panel R Runner
# Modes:
#   - upload_media : Upload image/video to Rubica, write result.json
#   - test         : Send a single test message to --test_number using first link in snapshot
#   - send         : Send full audience snapshot in parallel batches
#
# Token is passed ONLY via env var: RUBICA_TOKEN (never stored on disk)

args <- commandArgs(trailingOnly = TRUE)

get_arg <- function(flag, default = NA_character_) {
  idx <- which(args == flag)
  if (length(idx) == 0) return(default)
  if (idx == length(args)) return(default)
  return(args[idx + 1])
}

# ---- args -------------------------------------------------------------------

mode          <- get_arg("--mode", "send")  # send | test | upload_media

snapshot_path <- get_arg("--snapshot", NA_character_)   # test/send
service_id    <- get_arg("--service_id", NA_character_) # test/send

# message passed via file to support newlines + emojis reliably
message_file  <- get_arg("--message_file", NA_character_) # test/send
message_text  <- NA_character_
if (!is.na(message_file) && message_file != "") {
  message_text <- paste(readLines(message_file, warn = FALSE, encoding = "UTF-8"), collapse = "\n")
}

file_id       <- get_arg("--file_id", NA_character_)        # optional for test/send
test_number   <- get_arg("--test_number", NA_character_)    # test only

log_csv       <- get_arg("--log_csv", "rubika_message_log.csv") # test/send
batch_size    <- as.integer(get_arg("--batch_size", "1000"))
workers       <- as.integer(get_arg("--workers", "5"))
sleep_sec     <- as.numeric(get_arg("--sleep_sec", "0.2"))

# upload_media args
media_path    <- get_arg("--media_path", NA_character_)   # upload_media
media_type    <- get_arg("--media_type", NA_character_)   # upload_media: Image | Video
result_json   <- get_arg("--result_json", NA_character_)  # upload_media output json path

# ---- token ------------------------------------------------------------------

token <- Sys.getenv("RUBICA_TOKEN", unset = NA_character_)
if (is.na(token) || token == "") {
  stop("RUBICA_TOKEN env var is missing")
}

# ---- locate project + source functions --------------------------------------

get_script_dir <- function() {
  # Works for: Rscript path/to/run_campaign.R ...
  cmd <- commandArgs(trailingOnly = FALSE)
  hit <- grep("^--file=", cmd, value = TRUE)
  if (length(hit) > 0) {
    return(normalizePath(dirname(sub("^--file=", "", hit[1])), winslash = "/", mustWork = TRUE))
  }
  # Fallback: assume current working directory is project root (backend sets cwd)
  return(normalizePath(getwd(), winslash = "/", mustWork = TRUE))
}

script_dir <- get_script_dir()

# If we're actually inside .../r/runners then project root is two levels up
project_root <- script_dir
if (basename(script_dir) == "runners") {
  project_root <- normalizePath(file.path(script_dir, "..", ".."), winslash = "/", mustWork = TRUE)
}

# Source your Rubica functions library
source(file.path(project_root, "r", "lib", "rubicafunctions.R"))

# ---- helpers ----------------------------------------------------------------

read_snapshot <- function(path) {
  if (is.na(path) || path == "") stop("--snapshot is required")

  suppressPackageStartupMessages({
    library(readxl)
    library(data.table)
  })

  ext <- tolower(tools::file_ext(path))
  if (is.na(ext) || ext == "") stop("Snapshot path has no extension")

  if (ext %in% c("xlsx", "xls")) {
    df <- readxl::read_xlsx(path)
  } else if (ext == "csv") {
    df <- data.table::fread(path, showProgress = FALSE)
  } else {
    stop(paste("Unsupported snapshot extension:", ext))
  }

  df <- as.data.table(df)

  if (!("phone_number" %in% names(df))) stop("snapshot missing required column: phone_number")
  if (!("link" %in% names(df))) stop("snapshot missing required column: link")

  df[, phone_number := as.character(gsub("[^0-9]", "", as.character(phone_number)))]
  df[, link := as.character(link)]

  df <- df[!is.na(phone_number) & phone_number != "" & !is.na(link) & link != "", .(phone_number, link)]
  return(df)
}

norm_file_id <- function(x) {
  if (is.na(x) || x == "") return(NULL)
  return(x)
}

# ---- mode handlers -----------------------------------------------------------

handle_upload_media <- function() {
  if (is.na(media_path) || media_path == "") stop("--media_path is required in upload_media mode")
  if (is.na(media_type) || media_type == "") stop("--media_type is required in upload_media mode")
  if (!(media_type %in% c("Image", "Video"))) stop("--media_type must be Image or Video")
  if (is.na(result_json) || result_json == "") stop("--result_json is required in upload_media mode")

  suppressPackageStartupMessages({
    library(jsonlite)
  })

  file_name <- basename(media_path)

  req_up <- rubika_request_upload_file(
    token     = token,
    file_name = file_name,
    file_type = media_type
  )

  if (!identical(req_up$status, "OK")) {
    writeLines(
      jsonlite::toJSON(list(ok = FALSE, step = "requestUploadFile", resp = req_up), auto_unbox = TRUE),
      con = result_json,
      useBytes = TRUE
    )
    stop("requestUploadFile failed")
  }

  up_res <- rubika_upload_file(req_up$data$upload_url, media_path, token)

  fid <- tryCatch(up_res$data$file_id, error = function(e) NA_character_)
  if (is.na(fid) || fid == "") {
    writeLines(
      jsonlite::toJSON(list(ok = FALSE, step = "uploadFile", resp = up_res), auto_unbox = TRUE),
      con = result_json,
      useBytes = TRUE
    )
    stop("uploadFile failed: no file_id")
  }

  writeLines(
    jsonlite::toJSON(list(ok = TRUE, file_id = fid, file_name = file_name, file_type = media_type), auto_unbox = TRUE),
    con = result_json,
    useBytes = TRUE
  )

  cat("OK: media uploaded\n")
}

handle_test <- function() {
  if (is.na(service_id) || service_id == "") stop("--service_id is required")
  if (is.na(message_text) || message_text == "") stop("--message_file is required (and must not be empty)")
  if (is.na(test_number) || test_number == "") stop("--test_number required in test mode")

  df <- read_snapshot(snapshot_path)
  if (nrow(df) == 0) stop("No valid rows in snapshot after cleaning")

  # use first link for the test message
  test_df <- data.frame(
    phone_number = as.character(test_number),
    link = df$link[1]
  )

  send_rubika_in_batches(
    df            = test_df,
    token         = token,
    service_id    = service_id,
    text_template = message_text,
    scenario      = "CPA_Panel_TEST",
    batch_size    = 1,
    log_path_csv  = log_csv,
    sleep_sec     = 1,
    file_id       = norm_file_id(file_id)
  )

  cat("OK: test sent\n")
}

handle_send <- function() {
  if (is.na(service_id) || service_id == "") stop("--service_id is required")
  if (is.na(message_text) || message_text == "") stop("--message_file is required (and must not be empty)")

  df <- read_snapshot(snapshot_path)
  if (nrow(df) == 0) stop("No valid rows in snapshot after cleaning")

  send_rubika_in_batches_parallel(
    df            = df,
    token         = token,
    service_id    = service_id,
    text_template = message_text,
    scenario      = "CPA_Panel_SEND",
    batch_size    = batch_size,
    workers       = workers,
    log_path_csv  = log_csv,
    file_id       = norm_file_id(file_id),
    sleep_sec     = sleep_sec
  )

  cat("OK: campaign sent\n")
}

# ---- main -------------------------------------------------------------------

if (mode == "upload_media") {
  handle_upload_media()
} else if (mode == "test") {
  handle_test()
} else if (mode == "send") {
  handle_send()
} else {
  stop(paste("Unknown mode:", mode))
}
