@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1
set HTTPS_PROXY=http://127.0.0.1:7890
set HTTP_PROXY=http://127.0.0.1:7890
set https_proxy=http://127.0.0.1:7890
set http_proxy=http://127.0.0.1:7890
cd /d D:\2607compound
title CESM atm download - 6 shards via dap2 engine

echo ============================================================
echo  CESM1-LE TREFHT (daily, Europe box) - 6 parallel shards
echo  channel: built-in DAP2 client (python\dap2.py), NOT pydap
echo  expected: ~3 GB total, about 2 hours at ~480 kB/s aggregate
echo.
echo  Make sure the system proxy is ON and port 7890 is listening.
echo  Logs: logs\_cesm_dap2_shard1..6.log
echo ============================================================
echo.

start "cesm-shard1" /min cmd /c "python -u python\download_cesm1le.py gdex --engine dap2 --only-comp atm --member-ids 001,007,013,019 > logs\_cesm_dap2_shard1.log 2>&1"
start "cesm-shard2" /min cmd /c "python -u python\download_cesm1le.py gdex --engine dap2 --only-comp atm --member-ids 002,008,014,020 > logs\_cesm_dap2_shard2.log 2>&1"
start "cesm-shard3" /min cmd /c "python -u python\download_cesm1le.py gdex --engine dap2 --only-comp atm --member-ids 003,009,015     > logs\_cesm_dap2_shard3.log 2>&1"
start "cesm-shard4" /min cmd /c "python -u python\download_cesm1le.py gdex --engine dap2 --only-comp atm --member-ids 004,010,016     > logs\_cesm_dap2_shard4.log 2>&1"
start "cesm-shard5" /min cmd /c "python -u python\download_cesm1le.py gdex --engine dap2 --only-comp atm --member-ids 005,011,017     > logs\_cesm_dap2_shard5.log 2>&1"
start "cesm-shard6" /min cmd /c "python -u python\download_cesm1le.py gdex --engine dap2 --only-comp atm --member-ids 006,012,018     > logs\_cesm_dap2_shard6.log 2>&1"

echo 6 shards launched. Watch progress with:
echo     powershell -NoProfile -Command "Get-Content logs\_cesm_dap2_shard1.log -Tail 5"
echo Each shard prints one line per finished year, e.g.  [2007] 365 days
echo.
pause
