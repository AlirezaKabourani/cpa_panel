# install.packages(c("httr", "jsonlite"))
library(httr)
library(jsonlite)

rubika_api_call <- function(method, data = list(), token,
                            api_version = 1,
                            base_url = "https://messaging.rubika.ir") {
  req_body <- list(method = method, data = data, api_version = api_version)
  
  res <- POST(
    url = base_url,
    add_headers(
      "Content-Type" = "application/json",
      "Accept"       = "application/json",
      "token"        = token
    ),
    body = toJSON(req_body, auto_unbox = TRUE)
  )
  
  txt <- content(res, as = "text", encoding = "UTF-8")
  if (http_type(res) != "application/json") {
    return(list(http_status = status_code(res), raw = txt))
  }
  
  obj <- fromJSON(txt, simplifyVector = TRUE)
  obj$http_status <- status_code(res)
  obj$request  <- req_body
  obj
}




# Get account status (Active / Inactive + balance)
rubika_get_account_status <- function(token) {
  rubika_api_call(
    method = "getAccountStatus",
    data   = list(),
    token  = token
  )
}

# Check if a phone is registered & active on Rubika
rubika_get_phone_status <- function(token, phone) {
  rubika_api_call(
    method = "getPhoneStatus",
    data   = list(phone = phone),
    token  = token
  )
}


token <- "80498u98133uzaoj6ysf5j4qijy1yhgo37der8ramhm60r17juky4hog104ya833"

rubika_get_phone_status_row <- function(token, phone) {
  phone_chr <- as.character(phone)
  
  res <- tryCatch(
    rubika_get_phone_status(token, phone_chr),
    error = function(e) {
      list(
        status     = "ERROR",
        status_det = conditionMessage(e),
        data       = list(is_registered = NA, is_active = NA)
      )
    }
  )
  
  data.frame(
    phone_number  = phone_chr,
    status        = res$status        %||% NA_character_,
    status_det    = res$status_det    %||% NA_character_,
    is_registered = res$data$is_registered %||% NA,
    is_active     = res$data$is_active     %||% NA,
    stringsAsFactors = FALSE
  )
}



`%||%` <- function(x, y) if (is.null(x)) y else x


check_rubika_status_for_numbers <- function(token,
                                            numbers,
                                            out_csv    = "rubika_phone_status.csv",
                                            chunk_size = 10000,
                                            resume     = TRUE,
                                            sleep_sec  = 0.05) {
  # numbers: vector of phone numbers (integer64 or character)
  nums <- as.character(numbers)
  
  # RESUME: skip numbers already processed
  if (resume && file.exists(out_csv)) {
    message("Resume is TRUE and output file exists. Reading existing results to skip done numbers...")
    existing <- read.csv(out_csv, stringsAsFactors = FALSE, encoding = "UTF-8")
    done_set <- unique(existing$phone_number)
    to_do <- !nums %in% done_set
    nums <- nums[to_do]
    rm(existing, done_set)
  }
  
  n <- length(nums)
  if (n == 0) {
    message("Nothing to do: all numbers already processed.")
    return(invisible(NULL))
  }
  
  message(sprintf("Total numbers to process now: %d", n))
  
  # prepare chunk indices
  idx <- seq_len(n)
  chunk_ids <- split(idx, ceiling(idx / chunk_size))
  
  for (i in seq_along(chunk_ids)) {
    this_idx <- chunk_ids[[i]]
    this_nums <- nums[this_idx]
    
    message(sprintf("Processing chunk %d/%d (%d numbers)...",
                    i, length(chunk_ids), length(this_nums)))
    
    # call API for each number in this chunk
    chunk_res_list <- lapply(this_nums, function(p) {
      rubika_get_phone_status_row(token, p)
    })
    
    chunk_df <- do.call(rbind, chunk_res_list)
    
    # write / append to CSV
    if (!file.exists(out_csv)) {
      write.table(
        chunk_df,
        file         = out_csv,
        sep          = ",",
        row.names    = FALSE,
        col.names    = TRUE,
        append       = FALSE,
        qmethod      = "double",
        fileEncoding = "UTF-8"
      )
    } else {
      write.table(
        chunk_df,
        file         = out_csv,
        sep          = ",",
        row.names    = FALSE,
        col.names    = FALSE,
        append       = TRUE,
        qmethod      = "double",
        fileEncoding = "UTF-8"
      )
    }
    
    # small pause to be polite with the API
    if (sleep_sec > 0) Sys.sleep(sleep_sec)
  }
  
  invisible(NULL)
}






library(future)
library(future.apply)
library(filelock)

check_rubika_status_for_numbers_parallel <- function(token,
                                                     numbers,
                                                     out_csv    = "rubika_phone_status.csv",
                                                     chunk_size = 500,
                                                     workers    = 6,
                                                     resume     = TRUE,
                                                     sleep_sec  = 0.02,
                                                     max_chunks = Inf) {   # 👈 optional safety limit
  
  nums <- as.character(numbers)
  
  # ✅ RESUME
  if (resume && file.exists(out_csv)) {
    message("Resume enabled. Loading previous results...")
    existing <- read.csv(out_csv, stringsAsFactors = FALSE, encoding = "UTF-8")
    done_set <- unique(existing$phone_number)
    nums <- nums[!nums %in% done_set]
    rm(existing, done_set)
    gc()
  }
  
  n <- length(nums)
  if (n == 0) {
    message("Nothing to process.")
    return(invisible(NULL))
  }
  
  message(sprintf("Total numbers to process: %d", n))
  
  idx <- seq_len(n)
  chunk_ids <- split(idx, ceiling(idx / chunk_size))
  
  total_chunks <- min(length(chunk_ids), max_chunks)
  message(sprintf("Total chunks to process: %d", total_chunks))
  
  library(future)
  library(future.apply)
  library(filelock)
  
  plan(multisession, workers = workers)
  
  for (i in seq_len(total_chunks)) {
    
    this_idx  <- chunk_ids[[i]]
    this_nums <- nums[this_idx]
    
    message(sprintf(
      "Processing chunk %d / %d  (%d numbers)",
      i, total_chunks, length(this_nums)
    ))
    
    # ✅ PARALLEL PER-CHUNK
    res_list <- future_lapply(this_nums, function(p) {
      rubika_get_phone_status_row(token, p)
    }, future.seed = TRUE)
    
    chunk_df <- do.call(rbind, res_list)
    
    # ✅ FILE LOCK SAFE WRITE
    lock <- filelock::lock(paste0(out_csv, ".lock"))
    on.exit(filelock::unlock(lock), add = TRUE)
    
    if (!file.exists(out_csv)) {
      write.table(
        chunk_df,
        file         = out_csv,
        sep          = ",",
        row.names    = FALSE,
        col.names    = TRUE,
        append       = FALSE,
        qmethod      = "double",
        fileEncoding = "UTF-8"
      )
    } else {
      write.table(
        chunk_df,
        file         = out_csv,
        sep          = ",",
        row.names    = FALSE,
        col.names    = FALSE,
        append       = TRUE,
        qmethod      = "double",
        fileEncoding = "UTF-8"
      )
    }
    
    if (sleep_sec > 0) Sys.sleep(sleep_sec)
  }
  
  plan(sequential)
  message("✅ Parallel phone status scan finished.")
}



rubika_get_messages_status <- function(token, message_ids) {
  data <- list(
    message_ids = as.list(message_ids)  # ensure it becomes JSON array
  )
  
  rubika_api_call(
    method = "getMessagesStatus",
    data   = data,
    token  = token
  )
}

rubika_send_bulk_messages <- function(token, service_id, messages) {
  # messages: list of list(phone=..., text=..., file_id=...) 
  
  data <- list(
    service_id   = service_id,
    message_list = messages
  )
  
  rubika_api_call(
    method = "sendBulkMessages",
    data   = data,
    token  = token
  )
}

build_rubika_log <- function(send_result, status_result = NULL,
                             scenario      = NA_character_,
                             send_datetime = Sys.time()) {
  
  # 1) request messages (always available)
  msg_list <- send_result$request$data$message_list
  phones   <- vapply(msg_list, function(x) x$phone, "", USE.NAMES = FALSE)
  texts    <- vapply(msg_list, function(x) x$text,  "", USE.NAMES = FALSE)
  file_ids <- vapply(
    msg_list,
    function(x) if (!is.null(x$file_id)) x$file_id else NA_character_,
    character(1)
  )
  
  n_req <- length(phones)
  
  # 2) response message_status_list (may be NULL/empty/broken)
  msl <- NULL
  if (!is.null(send_result$data) && !is.null(send_result$data$message_status_list)) {
    msl <- send_result$data$message_status_list
  }
  
  # Normalize to data.frame if possible
  if (!is.null(msl) && !is.data.frame(msl)) {
    # try convert list -> data.frame safely
    msl <- tryCatch(as.data.frame(msl, stringsAsFactors = FALSE),
                    error = function(e) NULL)
  }
  
  # Prepare defaults
  message_id  <- rep(NA_character_, n_req)
  status_send <- rep(NA_character_, n_req)
  
  if (!is.null(msl) && nrow(msl) > 0) {
    # If API returned fewer rows than requested, fill what we have and keep NAs for the rest
    n_res <- nrow(msl)
    
    message_id[seq_len(min(n_req, n_res))]  <- as.character(msl$message_id[seq_len(min(n_req, n_res))])
    status_send[seq_len(min(n_req, n_res))] <- as.character(msl$status[seq_len(min(n_req, n_res))])
  }
  
  base_df <- data.frame(
    phone_number = phones,
    text         = texts,
    message_id   = message_id,
    status_send  = status_send,
    file_id      = file_ids,
    stringsAsFactors = FALSE
  )
  
  # 3) merge with latest statuses if we actually have message_ids
  log_df <- base_df
  log_df$status <- log_df$status_send
  
  have_ids <- !is.na(log_df$message_id) & log_df$message_id != ""
  
  if (!is.null(status_result) &&
      !is.null(status_result$data) &&
      !is.null(status_result$data$message_status_list) &&
      any(have_ids)) {
    
    st <- status_result$data$message_status_list
    if (!is.data.frame(st)) st <- tryCatch(as.data.frame(st, stringsAsFactors = FALSE),
                                           error = function(e) NULL)
    
    if (!is.null(st) && nrow(st) > 0) {
      status_df <- st[, c("message_id", "status")]
      names(status_df)[2] <- "status_final"
      
      merged <- merge(log_df, status_df, by = "message_id", all.x = TRUE)
      
      merged$status <- ifelse(
        is.na(merged$status_final) | merged$status_final == "",
        merged$status_send,
        merged$status_final
      )
      
      # restore original order (merge reorders)
      merged <- merged[match(log_df$message_id, merged$message_id), , drop = FALSE]
      log_df <- merged
    }
  }
  
  # 4) add scenario + time columns
  log_df$scenario  <- scenario
  log_df$send_data <- as.character(as.Date(send_datetime))
  log_df$send_time <- format(send_datetime, "%H:%M")
  
  # 5) final columns
  log_df <- log_df[, c("phone_number","message_id","file_id","status","text","scenario","send_data","send_time")]
  
  log_df
}

build_rubika_error_log <- function(batch_df,
                                   scenario,
                                   send_datetime,
                                   file_id = NULL,
                                   status_val = NA_character_,
                                   data_status_val = NA_character_) {
  # batch_df has phone_number, link
  n <- nrow(batch_df)
  
  status_text <- paste0(
    "SEND_ERROR: ",
    ifelse(is.na(status_val), "?", status_val),
    "/",
    ifelse(is.na(data_status_val), "?", data_status_val)
  )
  
  # mimic text construction in make_messages_from_df
  # (you can also pass text_template if you want to be 100% exact)
  # but simpler: store only phone + scenario marker
  log_df <- data.frame(
    phone_number = batch_df$phone_number,
    message_id   = NA_character_,        # no id from API
    file_id      = if (!is.null(file_id) && nzchar(file_id)) file_id else NA_character_,
    status       = status_text,
    text         = NA_character_,        # or you can reconstruct text if needed
    scenario     = scenario,
    send_data    = as.character(as.Date(send_datetime)),
    send_time    = format(send_datetime, "%H:%M"),
    stringsAsFactors = FALSE
  )
  
  log_df
}

save_rubika_log <- function(log_df, path = "rubika_message_log.csv") {
  # 1) ensure everything is UTF-8
  char_cols <- sapply(log_df, is.character)
  log_df[char_cols] <- lapply(log_df[char_cols], enc2utf8)
  
  # 2) Excel-safe text for phone_number and message_id
  if ("phone_number" %in% names(log_df)) {
    log_df$phone_number <- paste0("'", log_df$phone_number)
  }
  if ("message_id" %in% names(log_df)) {
    log_df$message_id <- paste0("'", log_df$message_id)
  }
  
  # 3) write CSV with UTF-8 BOM so Excel detects encoding
  if (!file.exists(path)) {
    write.table(
      log_df,
      file         = path,
      sep          = ",",
      row.names    = FALSE,
      col.names    = TRUE,
      append       = FALSE,
      qmethod      = "double",
      fileEncoding = "UTF-8"
    )
  } else {
    write.table(
      log_df,
      file         = path,
      sep          = ",",
      row.names    = FALSE,
      col.names    = FALSE,  # no header on append
      append       = TRUE,
      qmethod      = "double",
      fileEncoding = "UTF-8"
    )
  }
}

make_messages_from_df <- function(df,
                                  text_template,
                                  file_id = NULL) {
  # returns list of list(phone=..., text=..., file_id=...)
  n <- nrow(df)
  lapply(seq_len(n), function(i) {
    msg <- list(
      phone = df$phone_number[i],
      text  = sprintf(text_template, df$link[i])
    )
    
    # اگر file_id داده شده، برای همه پیام‌ها ست کن
    if (!is.null(file_id) && nzchar(file_id)) {
      msg$file_id <- file_id
    }
    
    msg
  })
}

send_rubika_in_batches <- function(df,
                                   token,
                                   service_id,
                                   text_template,
                                   scenario,
                                   batch_size   = 1000,
                                   log_path_csv = "rubika_message_log.csv",
                                   sleep_sec    = 1,
                                   file_id      = NULL) {
  n <- nrow(df)
  if (n == 0) {
    message("No rows to send.")
    return(invisible(NULL))
  }
  
  batch_ids <- split(seq_len(n), ceiling(seq_len(n) / batch_size))
  
  for (b in seq_along(batch_ids)) {
    idx      <- batch_ids[[b]]
    batch_df <- df[idx, , drop = FALSE]
    
    batch_time <- Sys.time()
    
    message(sprintf("Sending batch %d/%d (%d rows)...",
                    b, length(batch_ids), nrow(batch_df)))
    
    # 1) build messages for this batch
    messages <- make_messages_from_df(
      df            = batch_df,
      text_template = text_template,
      file_id       = file_id
    )
    
    # 2) send
    send_res <- rubika_send_bulk_messages(
      token      = token,
      service_id = service_id,
      messages   = messages
    )
    
    # ---- robust status check ----
    status_val      <- if (!is.null(send_res$status)) send_res$status else NA_character_
    data_status_val <- if (!is.null(send_res$data) && !is.null(send_res$data$status)) {
      send_res$data$status
    } else {
      NA_character_
    }
    
    status_ok <- (!is.na(status_val)      && identical(status_val, "OK"))
    done_ok   <- (!is.na(data_status_val) && identical(data_status_val, "Done"))
    
    if (!status_ok || !done_ok) {
      warning(sprintf(
        "Batch %d: sendBulkMessages returned unexpected status. status=%s, data$status=%s",
        b, as.character(status_val), as.character(data_status_val)
      ))
    }
    
    # 3) decide log mode: normal vs error-logging
    if (is.null(send_res$data$message_status_list) ||
        nrow(send_res$data$message_status_list) == 0) {
      
      warning(sprintf(
        "Batch %d: message_status_list is NULL or empty. Logging SEND_ERROR rows for this batch.",
        b
      ))
      
      # log each attempted message as SEND_ERROR
      log_df <- build_rubika_error_log(
        batch_df       = batch_df,
        scenario       = scenario,
        send_datetime  = batch_time,
        file_id        = file_id,
        status_val     = status_val,
        data_status_val = data_status_val
      )
      
    } else {
      # 4) get final status (Seen / Sent / …)
      msg_ids <- send_res$data$message_status_list$message_id
      
      status_res <- tryCatch(
        rubika_get_messages_status(token, msg_ids),
        error = function(e) {
          warning(sprintf("Batch %d: getMessagesStatus error: %s", b, conditionMessage(e)))
          NULL
        }
      )
      
      # 5) build normal log df with scenario + date/time
      log_df <- build_rubika_log(
        send_result   = send_res,
        status_result = status_res,
        scenario      = scenario,
        send_datetime = batch_time
      )
    }
    
    # 6) append to CSV log & assign to global
    assign(paste0("log_", scenario), log_df, envir = .GlobalEnv)
    save_rubika_log(log_df, log_path_csv)
    
    # 7) pause between batches
    if (b < length(batch_ids) && sleep_sec > 0) {
      Sys.sleep(sleep_sec)
    }
  }
}


refresh_rubika_status_df <- function(token,
                                     log_df,
                                     batch_size = 1000) {
  if (!"message_id" %in% names(log_df)) {
    stop("log_df must contain a 'message_id' column")
  }
  
  # ✅ Only real, non-empty, non-NA message_ids
  valid_idx <- !is.na(log_df$message_id) &
    log_df$message_id != "" &
    !grepl("^SEND_ERROR", log_df$status)
  
  if (!any(valid_idx)) {
    message("No valid message_id to refresh (all rows are SEND_ERROR / NA).")
    return(log_df)
  }
  
  all_ids <- unique(log_df$message_id[valid_idx])
  
  if (length(all_ids) == 0) {
    return(log_df)
  }
  
  id_batches <- split(all_ids, ceiling(seq_along(all_ids) / batch_size))
  
  all_status_list <- list()
  
  for (b in seq_along(id_batches)) {
    ids <- id_batches[[b]]
    
    message(sprintf(
      "Fetching status batch %d/%d (%d ids)...",
      b, length(id_batches), length(ids)
    ))
    
    res <- tryCatch(
      rubika_get_messages_status(token, ids),
      error = function(e) NULL
    )
    
    # ✅ FULL SAFETY CHECK
    if (is.null(res) ||
        is.null(res$status) ||
        res$status != "OK" ||
        is.null(res$data) ||
        is.null(res$data$message_status_list) ||
        length(res$data$message_status_list) == 0) {
      
      warning(sprintf(
        "Batch %d: getMessagesStatus returned invalid/empty response.",
        b
      ))
      next
    }
    
    st_df <- res$data$message_status_list[, c("message_id", "status")]
    names(st_df) <- c("message_id", "status_current")
    
    all_status_list[[b]] <- st_df
  }
  
  if (length(all_status_list) == 0) {
    warning("No status data returned from API.")
    return(log_df)
  }
  
  latest_status_df <- do.call(rbind, all_status_list)
  
  merged <- merge(log_df, latest_status_df,
                  by = "message_id",
                  all.x = TRUE)
  
  merged$status_at_send <- merged$status
  
  merged$status <- ifelse(
    is.na(merged$status_current) | merged$status_current == "",
    merged$status_at_send,
    merged$status_current
  )
  
  col_order <- c("phone_number",
                 "message_id",
                 "file_id",
                 "status",
                 "text",
                 "scenario",
                 "send_data",
                 "send_time")
  
  col_order <- intersect(col_order, names(merged))
  merged <- merged[, c(col_order, setdiff(names(merged), col_order))]
  
  merged
}


refresh_rubika_status_file <- function(token,
                                       log_path_in  = "rubika_message_log.csv",
                                       log_path_out = "rubika_message_log.csv",
                                       batch_size   = 1000,
                                       scenarios    = NULL) {
  if (!file.exists(log_path_in)) {
    stop("Input log file does not exist: ", log_path_in)
  }
  
  log_df <- read.csv(
    log_path_in,
    stringsAsFactors = FALSE,
    encoding = "UTF-8"
  )
  
  # remove Excel quotes for internal use
  log_df$phone_number <- gsub("^'", "", log_df$phone_number)
  log_df$message_id   <- gsub("^'", "", log_df$message_id)
  
  # حفظ ترتیب اصلی ردیف‌ها
  log_df$row_id <- seq_len(nrow(log_df))
  
  if (!is.null(scenarios)) {
    # فقط سناریوهای مورد نظر
    idx_update <- log_df$scenario %in% scenarios
    
    if (!any(idx_update)) {
      warning("No rows found for the given scenarios. Nothing updated.")
      updated_df <- log_df
    } else {
      df_update <- log_df[idx_update, , drop = FALSE]
      df_keep   <- log_df[!idx_update, , drop = FALSE]
      
      message(sprintf("Refreshing %d rows for scenarios: %s",
                      nrow(df_update),
                      paste(unique(df_update$scenario), collapse = ", ")))
      
      df_update_new <- refresh_rubika_status_df(
        token     = token,
        log_df    = df_update,
        batch_size = batch_size
      )
      
      # ترکیب مجدد و برگرداندن به ترتیب اولیه
      updated_df <- rbind(df_update_new, df_keep)
      updated_df <- updated_df[order(updated_df$row_id), ]
    }
  } else {
    # رفرش کل فایل (رفتار قبلی)
    updated_df <- refresh_rubika_status_df(
      token     = token,
      log_df    = log_df,
      batch_size = batch_size
    )
  }
  
  # row_id دیگر لازم نیست در خروجی
  updated_df$row_id <- NULL
  
  # برگرداندن به UTF-8 و آماده‌سازی برای Excel
  char_cols <- sapply(updated_df, is.character)
  updated_df[char_cols] <- lapply(updated_df[char_cols], enc2utf8)
  
  if ("phone_number" %in% names(updated_df)) {
    updated_df$phone_number <- paste0("'", updated_df$phone_number)
  }
  if ("message_id" %in% names(updated_df)) {
    updated_df$message_id <- paste0("'", updated_df$message_id)
  }
  
  write.table(
    updated_df,
    file         = log_path_out,
    sep          = ",",
    row.names    = FALSE,
    col.names    = TRUE,
    append       = FALSE,
    qmethod      = "double",
    fileEncoding = "UTF-8"
  )
  
  invisible(updated_df)
}


rubika_request_upload_file <- function(token,
                                       file_name,
                                       file_type = c("File", "Image", "Video", "Voice", "Music")) {
  file_type <- match.arg(file_type)
  
  data <- list(
    file_name = file_name,  
    file_type = file_type 
  )
  
  rubika_api_call(
    method = "requestUploadFile",
    data   = data,
    token  = token
  )
}
rubika_upload_file <- function(upload_url, file_path, token) {
  try_one <- function(field_name) {
    res <- httr::POST(
      url    = upload_url,
      body   = setNames(
        list(httr::upload_file(file_path)),
        field_name
      ),
      encode = "multipart",
      httr::add_headers(
        token = token
      )
    )
    
    raw_txt <- httr::content(res, as = "text", encoding = "UTF-8")
    cat(sprintf("uploadFile raw response with field '%s':\n%s\n\n",
                field_name, raw_txt))
    
    obj <- tryCatch(
      jsonlite::fromJSON(raw_txt, simplifyVector = TRUE),
      error = function(e) list(status = NA, raw = raw_txt)
    )
    obj
  }
  
  # 1) اول طبق مستند: files=[file]
  res1 <- try_one("files")
  if (!is.null(res1$status) && identical(res1$status, "OK")) {
    return(res1)
  }
  
  # 2) اگر جواب OK نشد، با "file" امتحان کن
  res2 <- try_one("file")
  return(res2)
}


# send parallel
# fix step showing:
library(future)
library(future.apply)
library(progressr)
library(filelock)

send_rubika_in_batches_parallel <- function(df,
                                            token,
                                            service_id,
                                            text_template,
                                            scenario,
                                            batch_size   = 1000,
                                            workers      = 10,
                                            log_path_csv = "rubika_message_log.csv",
                                            file_id      = NULL,
                                            sleep_sec    = 0.2) {
  
  n <- nrow(df)
  if (n == 0) {
    message("No rows to send.")
    return(invisible(NULL))
  }
  
  batch_ids <- split(seq_len(n), ceiling(seq_len(n) / batch_size))
  total_batches <- length(batch_ids)
  
  message(sprintf(
    "Starting PARALLEL send: %d batches × %d workers × %d msgs/batch",
    total_batches, workers, batch_size
  ))
  
  plan(multisession, workers = workers)
  
  progressr::handlers(global = TRUE)
  progressr::with_progress({
    p <- progressr::progressor(steps = total_batches)
    
    future_lapply(seq_along(batch_ids), function(b) {
      
      idx <- batch_ids[[b]]
      batch_df <- df[idx, , drop = FALSE]
      batch_time <- Sys.time()
      
      # 1) Build messages
      messages <- make_messages_from_df(
        df            = batch_df,
        text_template = text_template,
        file_id       = file_id
      )
      
      # 2) Send
      send_res <- rubika_send_bulk_messages(
        token      = token,
        service_id = service_id,
        messages   = messages
      )
      
      status_val <- if (!is.null(send_res$status)) send_res$status else NA_character_
      data_status_val <- if (!is.null(send_res$data) && !is.null(send_res$data$status)) {
        send_res$data$status
      } else {
        NA_character_
      }
      
      # 3) Build log
      msl <- send_res$data$message_status_list
      
      msl_ok <- !is.null(msl) &&
        is.data.frame(msl) &&
        nrow(msl) > 0 &&
        "message_id" %in% names(msl) &&
        any(!is.na(msl$message_id) & msl$message_id != "")
      
      if (!msl_ok) {
        
        log_df <- build_rubika_error_log(
          batch_df        = batch_df,
          scenario        = scenario,
          send_datetime   = batch_time,
          file_id         = file_id,
          status_val      = status_val,
          data_status_val = data_status_val
        )
        
      } else {
        
        msg_ids <- msl$message_id
        
        status_res <- tryCatch(
          rubika_get_messages_status(token, msg_ids),
          error = function(e) NULL
        )
        
        log_df <- build_rubika_log(
          send_result   = send_res,
          status_result = status_res,
          scenario      = scenario,
          send_datetime = batch_time
        )
      }
      
      
      # 4) SAFE CSV WRITE (lock)
      lock <- filelock::lock(paste0(log_path_csv, ".lock"))
      on.exit(filelock::unlock(lock), add = TRUE)
      save_rubika_log(log_df, log_path_csv)
      
      if (sleep_sec > 0) Sys.sleep(sleep_sec)
      
      # ✅ report progress from worker to main session
      p(sprintf("Batch %d/%d", b, total_batches))
      
      invisible(TRUE)
    }, future.seed = TRUE)
  })
  
  plan(sequential)
  message("✅ Parallel sending finished.")
}



add_phone_every_step <- function(df, scenario, phone = "989024004940", step = 1000) {
  stopifnot(all(c("phone_number", "link") %in% names(df)))
  
  n <- nrow(df)
  if (n == 0) {
    return(rbind(
      data.frame(phone_number = phone, link = paste0(scenario, "_begin")),
      data.frame(phone_number = phone, link = paste0(scenario, "_end"))
    ))
  }
  
  # Split df into chunks of size `step`
  grp <- (seq_len(n) - 1) %/% step + 1
  chunks <- split(df, grp)
  
  out <- list()
  out[[1]] <- data.frame(phone_number = phone, link = paste0(scenario, "_begin"))
  
  for (g in seq_along(chunks)) {
    out[[length(out) + 1]] <- chunks[[g]]
    
    # Insert marker after each full step block, except after the last block
    if (g < length(chunks)) {
      out[[length(out) + 1]] <- data.frame(
        phone_number = phone,
        link = paste0(scenario, "_step_", g * step)
      )
    }
  }
  
  out[[length(out) + 1]] <- data.frame(phone_number = phone, link = paste0(scenario, "_end"))
  
  do.call(rbind, out)
}
