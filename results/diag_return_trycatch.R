f <- function() {
  res <- tryCatch({ return(NULL) }, error = function(e) "err")
  "after-trycatch"
}
cat("f() returns: "); print(f())

# 模拟 detect_events.R 的场景: process_chunk 在 tryCatch 内 return(NULL)
process_chunk_sim <- function(has_event) {
  out <- vector("list", 2)
  for (k in 1:2) {
    res <- tryCatch({
      e <- if (has_event && k == 1) data.frame(event_no = 1) else NULL
      if (is.null(e) || nrow(e) == 0L) return(NULL)   # <-- 关键行
      data.frame(x = 1)
    }, error = function(err) NULL)
    out[[k]] <- res
  }
  list(events = do.call(rbind, out), n_ok = 2L)
}
r <- process_chunk_sim(has_event = FALSE)
cat("sim r = "); print(r)
cat("r$events = "); print(if (is.null(r)) "R-IS-NULL (whole function returned)" else r$events)
cat("r$n_ok  = "); print(if (is.null(r)) "N/A" else r$n_ok)
# worker 侧
v <- c(n_events = if (is.null(r$events)) 0L else nrow(r$events), n_ok = r$n_ok)
cat("worker vector = "); print(v)
cat("v[['n_ok']] exists: ", "n_ok" %in% names(v), "\n")
