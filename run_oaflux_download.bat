@echo off
chcp 65001 >nul
title OAFlux evaporation download (WHOI / NOAA-PSL / APDRC)
cd /d D:\2607compound
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1
echo ============================================================
echo  OAFlux monthly evaporation 1991-2020  (fig.5b input)
echo  independent of the ERA5/CDS job - safe to run in parallel
echo  log file: D:\2607compound\logs\oaflux_download.log
echo ============================================================
echo.
echo [1/2] probing mirrors (no download) ...
python python\download_oaflux_evap.py --probe
echo.
echo [2/2] downloading 1991-2020 ...
python python\download_oaflux_evap.py --log logs\oaflux_download.log
echo.
echo === finished. Press any key to close ===
pause >nul
