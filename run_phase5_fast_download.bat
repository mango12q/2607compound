@echo off
REM ===========================================================================
REM  ERA5 fast download - ONE visible window, ONE script at a time.
REM  Step 0: adopt_cds_jobs.py  - harvest jobs CDS finished while we were away
REM          (a year is only written once; already-present months are skipped)
REM  Step 1: download_era5_fast.py --only both - tmax first, then sp, in this
REM          same python process (both are the same CDS dataset, and CDS caps
REM          how many requests from one dataset may sit in the queue).
REM          Years that are still queued on CDS are skipped, so a restart
REM          never re-queues the same year twice.
REM
REM  Resumable: close the window any time, re-run this bat, done months skip.
REM  Log: D:\2607compound\logs\era5_fast_download.log            (UTF-8)
REM  Queue ledger: D:\2607compound\logs\era5_pending_years.json  (auto)
REM ===========================================================================
chcp 65001 >nul
title ERA5 download - harvest CDS first, then tmax + sp (3 jobs, auto-loop)
cd /d D:\2607compound

REM UTF-8 everywhere, so Chinese and box-drawing output is not mojibake.
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1

echo ============================================================
echo  ERA5 daily-statistics download
echo   dataset: derived-era5-single-levels-daily-statistics
echo.
echo   step 0/2 : harvest jobs CDS finished while we were away
echo   step 1/2 : tmax 0.25deg Europe 1984-2023
echo   step 2/2 : sp   0.25deg Europe 1984-2023
echo.
echo  scheduling  : a year already queued on CDS is skipped (no duplicates)
echo                the request of every queued job is read back from CDS,
echo                so even a lost POST response cannot cause a second queue slot
echo  in-run      : every 10 min this run also harvests jobs CDS has finished
echo  loop        : when a pass ends with months still missing, it waits 10 min
echo                and plans again - the window stays open during congestion
echo  granularity : 1 year per CDS request
echo  concurrency : 3 requests in flight  (CDS caps queued requests per dataset)
echo  heartbeat   : one line every 5 minutes while waiting in the queue
echo                (a long quiet stretch = queued, not stuck)
echo.
echo  Resumable - close this window any time and re-run this bat.
echo  Log file    : D:\2607compound\logs\era5_fast_download.log
echo ============================================================
echo.

echo --- step 0/2 : harvest finished CDS jobs ---
REM  168h (7 days) window: the PC may have been off for a while, and a job that
REM  finished while it was off can easily be older than 24-72h.
python python\adopt_cds_jobs.py --max-jobs 10 --since-hours 168
echo.
echo --- step 1-2/2 : download tmax then sp ---
python python\download_era5_fast.py --only both --jobs 3 --loop-minutes 10 --log logs\era5_fast_download.log
set RC=%ERRORLEVEL%

echo.
echo ============================================================
echo  finished (completed or interrupted), exit code = %RC%
echo  next check : python python\phase5_humid.py check
echo  press any key to close this window
echo ============================================================
pause >nul
exit /b %RC%
