@echo off
chcp 65001 >nul
REM ===========================================================================
REM  Phase 6 (CESM1-LE GHG attribution, Fig.3-4): download all 20 members
REM
REM  Usage   : double-click this file, or run  run_phase6_download.bat  in cmd
REM  Content : ALL + XGHG, 20 members, daily TREFHT and SST, 2000-2021
REM
REM  HOW IT WORKS (changed 2026-10-20):
REM    Step 1 uses NCAR GDEX **OPeNDAP server-side slicing**: the server cuts
REM    the 2000-2021 window (and, for the atmosphere, the Europe box) before
REM    sending, so only a few tens of MB move per member/experiment.  It writes
REM    the final proc files directly:
REM       trefht_all_<mem>_2000-2021.nc    sst_all_<mem>_2000-2021.nc
REM       trefht_xghg_<mem>_2000-2021.nc   sst_xghg_<mem>_2000-2021.nc
REM    That is 4 files x 20 members = 80 groups.
REM
REM    The old Step 1 (AWS zarr slice, s3://ncar-cesm-lens) is NO LONGER USED:
REM    on 2026-10-20 it hung forever inside ds.load() (zero bytes read for
REM    60+ min; S3 direct is blocked here and the proxy link to S3 stalls).
REM    GDEX has ALL TREFHT as well, so the zarr step is redundant.
REM
REM  Volume  : ~10-30 GB of proc files, hours to a day over the proxy
REM            do NOT switch to the raw full-period path (~750 GB; does not fit)
REM  After   : python python\phase6_cesm.py pairs
REM            python python\phase6_cesm.py prepare  --members 20
REM            python python\phase6_cesm.py detect   --members 20 --baseline xghg --loo --tag _v4
REM            python python\phase6_cesm.py compound --members 20 --tag _v4 --compound-def envelope
REM            python python\phase6_cesm.py attrib   --members 20 --tag _v4 --compound-def envelope
REM
REM  NOTE: this file is deliberately ASCII-only. cmd.exe mis-parses UTF-8 Chinese
REM  text in .bat files (it turned two header lines into "command not found"
REM  errors on 2026-10-20), so all console text here is English.
REM ===========================================================================
title Phase 6 download - CESM1-LE 20 members via GDEX OPeNDAP
cd /d D:\2607compound

echo ============================================================
echo  CESM1-LE download  (members 001-020, ALL + XGHG, 2000-2021)
echo.
echo   Step 1/2: GDEX OPeNDAP slice -^> proc files   (the real work)
echo   Step 2/2: trim raw whole files (skipped unless raw\*.nc exist)
echo.
echo   Output           : E:\2607compound\data\CESM1-LE\proc
echo   Already done     : 21 files (~14 GB) from members 001-003
echo   Remaining        : 80 groups - those already present are skipped
echo.
echo   Resumable: close the window any time, re-run this bat,
echo              finished groups are skipped (output file exists = done).
echo.
echo   Network note: uses the system proxy (127.0.0.1:7890) via env vars.
echo ============================================================
echo.

echo --- preflight: python packages ---
python -c "import zarr, s3fs, xarray, netCDF4" 2>nul
if errorlevel 1 goto :deps
echo     OK: zarr / s3fs / xarray / netCDF4 all importable
echo.

echo  Optional dry check (lists the GDEX segments, downloads nothing):
echo    python python\download_cesm1le.py gdex --members 20 --list
echo.
echo  Starting step 1/2 in 10 seconds ...   (press a key to start now, Ctrl-C to stop)
timeout /t 10 >nul

echo.
echo [1/2] GDEX OPeNDAP slice: TREFHT + SST, ALL + XGHG, 20 members ...
python python\download_cesm1le.py gdex --members 20
if errorlevel 1 goto :err

echo.
echo [2/2] trim raw whole files (only if any) ...
dir /b "D:\2607compound\data\CESM1-LE\raw\*.nc" >nul 2>&1
if errorlevel 1 (
  echo     no raw whole files - nothing to trim, skipped.
) else (
  python python\download_cesm1le.py trim
  if errorlevel 1 goto :err
)

echo.
echo ============================================================
echo  ALL DONE. Check D:\2607compound\data\CESM1-LE\proc
echo  Expect 4 files per member: trefht_all, trefht_xghg, sst_all, sst_xghg.
echo  Tell the assistant "CESM full done" to start the full
echo  Phase 6 attribution run (Fig.3 - Fig.4).
echo ============================================================
pause
exit /b 0

:deps
echo.
echo ============================================================
echo  MISSING PYTHON PACKAGE. Install it, then re-run this bat:
echo     python -m pip install zarr
echo     (already in requirements.txt; s3fs / xarray / netCDF4 must import too)
echo ============================================================
pause
exit /b 3

:err
echo.
echo ============================================================
echo  A STEP FAILED. Window stays open.
echo  Resumable - fix the cause and re-run this bat.
echo ============================================================
pause
exit /b 1
