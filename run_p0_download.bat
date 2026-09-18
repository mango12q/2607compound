@echo off
chcp 65001 >nul
title CESM1-LE P0 download (3 members)
cd /d D:\2607compound

echo ============================================================
echo  CESM1-LE P0 download  (members 001-003, ALL + XGHG, 2000-2021)
echo  Step 1/3: ALL TREFHT via AWS zarr slice        (~30 min)
echo  Step 2/3: SST + XGHG whole files via proxy     (~11 h)
echo  Step 3/3: trim whole files to 2000-2021        (~10 min)
echo  Output:   E:\2607compound\data\CESM1-LE\proc
echo  Disk needed: ~90 GB on E:
echo.
echo  Safe to close this window at any time:
echo  just double-click this bat again, finished parts are skipped.
echo ============================================================
echo.

echo [1/3] AWS zarr slice: ALL daily TREFHT ...
python python\download_cesm1le.py aws --members 3
if errorlevel 1 goto :err

echo.
echo [2/3] fileServer whole files: SST + XGHG ...
python python\download_cesm1le.py download --urls results\tables\cesm1le_p0_urls.csv
if errorlevel 1 goto :err

echo.
echo [3/3] trim to 2000-2021 ...
python python\download_cesm1le.py trim
if errorlevel 1 goto :err

echo.
echo ============================================================
echo  ALL DONE. Check: data\CESM1-LE\proc  (expect 15 files:
echo  3x TREFHT_all_* + 6 SST/XGHG groups trimmed)
echo  Tell the assistant: "P0 done" to start Phase 6 pipeline.
echo ============================================================
pause
exit /b 0

:err
echo.
echo A STEP FAILED. The window stays open. Fix or just re-run this
echo bat - finished parts are skipped automatically (resume).
pause
