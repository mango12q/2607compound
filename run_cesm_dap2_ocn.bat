@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1
title CESM1-LE ocean SST - DAP2 client, 6 shards (members 001-020)
cd /d D:\2607compound

rem ---------------------------------------------------------------
rem  CESM1-LE ocean SST download: built-in DAP2 client + 6 shards
rem  - transfers ONLY the Europe-neighbour POP sub-grid slab
rem      (9.2 percent of points), then pads back to global shape
rem      single group 3.9 GB -> ~0.36 GB ; 40 groups 158 GB -> ~15 GB
rem  - proxy: system proxy registry is OFF on this machine, so set
rem      HTTPS_PROXY explicitly, otherwise it goes direct (very slow)
rem  - existing outputs are skipped; safe to close and re-run anytime
rem  - this file is pure ASCII on purpose: cmd.exe mis-parses UTF-8
rem ---------------------------------------------------------------

set HTTPS_PROXY=http://127.0.0.1:7890
set HTTP_PROXY=http://127.0.0.1:7890
set https_proxy=http://127.0.0.1:7890
set http_proxy=http://127.0.0.1:7890

echo ============================================================
echo  CESM1-LE ocn SST  --  engine: DAP2 client (python\dap2.py)
echo  proxy : %HTTPS_PROXY%
echo  out   : data\CESM1-LE\proc\   sst_all_XXX_2000-2021.nc
echo  logs  : logs\_cesm_dap2_ocn_shard1..6.log
echo ============================================================
echo.

start "cesm-ocn-shard1" /min cmd /c "python -u python\download_cesm1le.py gdex --engine dap2 --only-comp ocn --member-ids 001,007,013,019 > logs\_cesm_dap2_ocn_shard1.log 2>&1"
timeout /t 3 /nobreak >nul
start "cesm-ocn-shard2" /min cmd /c "python -u python\download_cesm1le.py gdex --engine dap2 --only-comp ocn --member-ids 002,008,014,020 > logs\_cesm_dap2_ocn_shard2.log 2>&1"
timeout /t 3 /nobreak >nul
start "cesm-ocn-shard3" /min cmd /c "python -u python\download_cesm1le.py gdex --engine dap2 --only-comp ocn --member-ids 003,009,015 > logs\_cesm_dap2_ocn_shard3.log 2>&1"
timeout /t 3 /nobreak >nul
start "cesm-ocn-shard4" /min cmd /c "python -u python\download_cesm1le.py gdex --engine dap2 --only-comp ocn --member-ids 004,010,016 > logs\_cesm_dap2_ocn_shard4.log 2>&1"
timeout /t 3 /nobreak >nul
start "cesm-ocn-shard5" /min cmd /c "python -u python\download_cesm1le.py gdex --engine dap2 --only-comp ocn --member-ids 005,011,017 > logs\_cesm_dap2_ocn_shard5.log 2>&1"
timeout /t 3 /nobreak >nul
start "cesm-ocn-shard6" /min cmd /c "python -u python\download_cesm1le.py gdex --engine dap2 --only-comp ocn --member-ids 006,012,018 > logs\_cesm_dap2_ocn_shard6.log 2>&1"

echo.
echo  6 shards launched in minimized windows.
echo  Check progress:  powershell -c "gc logs\_cesm_dap2_ocn_shard1.log -Tail 5"
echo.
pause
