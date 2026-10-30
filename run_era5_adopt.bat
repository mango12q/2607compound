@echo off
REM ===========================================================================
REM  Adopt CDS jobs that FINISHED server-side while this PC was off / offline.
REM
REM  The CDS queue keeps running when you close the window or shut down the PC,
REM  so year-requests submitted earlier may already be "successful".  The normal
REM  downloader never looks at them (it re-submits whatever months are missing),
REM  so they would be wasted.  This bat downloads their results, splits them into
REM  monthly files and verifies each month.
REM
REM  Run this BEFORE run_phase5_fast_download.bat.
REM  NEVER run "download_era5_fast.py --clean-queue" before this: that deletes
REM  the queued jobs and there is nothing left to adopt.
REM
REM  State of already-adopted jobIDs: logs\cds_adopted_jobs.json
REM ===========================================================================
chcp 65001 >nul
title ERA5 resume - adopt CDS jobs finished while the PC was off
cd /d D:\2607compound

REM UTF-8 everywhere, so Chinese and box-drawing output is not mojibake.
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1

echo ============================================================
echo  step 0/2 : adopt CDS jobs that finished while we were away
echo             (download result -^> split into months -^> verify)
echo ============================================================
echo.
REM  168h (7 days) window: the PC may have been off for a while, and a job that
REM  finished while it was off can easily be older than 24-72h.
python python\adopt_cds_jobs.py --max-jobs 10 --since-hours 168
set RC=%ERRORLEVEL%
echo.
echo ============================================================
echo  adopt finished, exit code = %RC%
echo  next : run_phase5_fast_download.bat   (it will skip the months just adopted)
echo  press any key to close this window
echo ============================================================
pause >nul
exit /b %RC%
