@echo off
chcp 65001 >nul
title Phase 5 downloads - ERA5 tmax / ERA5 sp 0.25 / OAFlux
cd /d D:\2607compound

echo ============================================================
echo  Phase 5 (humid-heat stress) input downloads
echo.
echo   1/3  ERA5 tmax  0.25deg Europe  1984-2023   ~1-2 GB
echo   2/3  ERA5 sp    0.25deg Europe  1984-2023   ~1 GB     [dataset 3b+]
echo   3/3  OAFlux     evap 1991-2020              ~100 MB
echo.
echo  Disk target: E:\2607compound\data\ERA5, E:\2607compound\data\OAFlux
echo  All three are resumable: just re-run this bat, finished parts skip.
echo.
echo  PREREQ (one-off):
echo    - pip install cdsapi        + valid ~/.cdsapirc
echo    - accept CC-BY terms once on the CDS dataset page
echo.
echo  TIP: run "python python\download_era5_sp025.py --dry-run" first
echo       to see the plan without downloading anything.
echo ============================================================
echo.
pause

echo.
echo [1/3] ERA5 daily maximum 2m temperature (0.25deg, Europe) ...
python python\download_era5_tmax.py
if errorlevel 1 goto :err

echo.
echo [1b/3] merge tmax monthly files ...
python python\download_era5_tmax.py --merge
if errorlevel 1 goto :err

echo.
echo [2/3] ERA5 surface pressure (0.25deg, Europe) ...
python python\download_era5_sp025.py
if errorlevel 1 goto :err

echo.
echo [2b/3] merge sp monthly files ...
python python\download_era5_sp025.py --merge
if errorlevel 1 goto :err

echo.
echo [3/3] OAFlux ocean evaporation (monthly, 1deg) ...
python python\download_oaflux_evap.py
if errorlevel 1 goto :err

echo.
echo ============================================================
echo  ALL DONE. Expected new files:
echo    data\ERA5\ERA5_tmax_1984_2023_daily.nc
echo    data\ERA5\ERA5_sp_1984_2023_daily.nc
echo    data\OAFlux\OAFlux_evap_1991_2020_monthly.nc
echo.
echo  Next: Phase 5 pipeline (WBT - SH - Fig.5 - Fig.6).
echo  Tell the assistant: "Phase 5 data ready".
echo ============================================================
pause
exit /b 0

:err
echo.
echo A STEP FAILED. Window stays open.
echo All three downloads are resumable - just re-run this bat.
pause
