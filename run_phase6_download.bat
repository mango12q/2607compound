REM ===========================================================================
REM  Phase 6（CESM1-LE GHG 归因，图3-4）全量 20 成员下载
REM
REM  用法：双击本文件，或在 cmd 里执行  run_phase6_download.bat
REM  内容：ALL + XGHG 各 20 成员的日值 TREFHT 与 SST，2000-2021
REM  预估：~750 GB / 4-5 天（断点续传，可反复中断重跑）
REM  只想先跑 3 个成员验证管线：用 run_p0_download.bat
REM  下载完成后依次执行（口径已定，见 results/复现报告.md §5 D7）：
REM     python python\phase6_cesm.py pairs
REM     python python\phase6_cesm.py prepare  --members 20
REM     python python\phase6_cesm.py detect   --members 20 --baseline xghg --loo --tag _v4
REM     python python\phase6_cesm.py compound --members 20 --tag _v4 --compound-def envelope
REM     python python\phase6_cesm.py attrib   --members 20 --tag _v4 --compound-def envelope
REM ===========================================================================
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
