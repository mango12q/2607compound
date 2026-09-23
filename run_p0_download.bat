REM ===========================================================================
REM  Phase 6 冒烟测试用：只下 CESM1-LE 前 3 个成员（ALL + XGHG）
REM
REM  用法：双击本文件，或在 cmd 里执行  run_p0_download.bat
REM  用途：管线联调；跑通后再用 run_phase6_download.bat 下全量 20 成员
REM  预估：~100-120 GB / 13-15 小时（断点续传）
REM ===========================================================================
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
