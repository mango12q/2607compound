REM ===========================================================================
REM  Phase 5（湿热应力，图5-6）输入数据一键下载
REM
REM  用法：双击本文件，或在 cmd 里执行  run_phase5_downloads.bat
REM  内容（依次跑三个下载脚本，可中断后续传）：
REM     1) ERA5 日最高气温 tmax  0.25° 欧洲框   python\download_era5_tmax.py
REM     2) ERA5 地表气压 sp      0.25° 欧洲框   python\download_era5_sp025.py
REM     3) OAFlux 月度蒸发       1°   全球      python\download_oaflux_evap.py
REM  前置：CDS 账号，凭据在 %USERPROFILE%\.cdsapirc（ERA5 两项需要；OAFlux 不需要）
REM  预估：几小时（取决于网络；断点续传，可重复运行）
REM  想看"要下多少"而不下载：分别跑各脚本的 --dry-run / --probe
REM ===========================================================================
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
