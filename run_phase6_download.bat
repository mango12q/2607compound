@echo off
chcp 65001 >nul
title Phase 6 download - CESM1-LE full 20 members (ALL + XGHG)
cd /d D:\2607compound

echo ============================================================
echo  CESM1-LE full download  (members 001-020, ALL + XGHG, 2000-2021)
echo.
echo   Step 1/3: ALL daily TREFHT via AWS zarr slice     fast
echo   Step 2/3: SST + XGHG whole files via proxy        ~4-5 days
echo   Step 3/3: trim whole files to 2000-2021           ~1 h
echo.
echo   Currently on disk: members 001-003 only (~123 GB)
echo   Remaining        : ~17 members  (~750 GB budget)
echo   Disk needed      : plan for ~800 GB free on E:
echo   Output           : E:\2607compound\data\CESM1-LE\proc
echo.
echo   Resumable: close the window any time, re-run this bat,
echo              finished members/files are skipped.
echo.
echo   Network note: the project uses the system proxy
echo                 (127.0.0.1:6789). Direct connection is ~100x slower.
echo ============================================================
echo.
echo  DRY CHECK FIRST (recommended, downloads nothing):
echo    python python\download_cesm1le.py gdex --members 20 --list
echo.
pause

echo.
echo [1/3] AWS zarr slice: ALL daily TREFHT (20 members) ...
python python\download_cesm1le.py aws --members 20
if errorlevel 1 goto :err

echo.
echo [2/3] GDEX whole files: SST + XGHG (20 members) ...
python python\download_cesm1le.py gdex --members 20
if errorlevel 1 goto :err

echo.
echo [3/3] trim to 2000-2021 ...
python python\download_cesm1le.py trim
if errorlevel 1 goto :err

echo.
echo ============================================================
echo  ALL DONE. Check data\CESM1-LE\proc
echo  Tell the assistant: "CESM full done" to start the full
echo  Phase 6 attribution run (Fig.3 - Fig.4).
echo ============================================================
pause
exit /b 0

:err
echo.
echo A STEP FAILED. Window stays open.
echo Resumable - fix the cause and re-run this bat.
pause
