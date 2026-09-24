@echo off
REM ============================================================================
REM  run_all_phases.bat — 全流程一键入口（Phase 0 → Phase 7）
REM
REM  用法：
REM      run_all_phases.bat                跑能跑的全部（缺数据自动跳过）
REM      run_all_phases.bat --dry-run      只看将执行哪些命令
REM      run_all_phases.bat --phases 5     只跑 Phase 5（图5/图6）
REM      run_all_phases.bat --tag _v4      Phase 6 的产物后缀
REM
REM  数据下载（耗时最长，建议先挂上）：
REM      run_phase5_downloads.bat          ERA5 tmax + sp0.25° + OAFlux（~3 GB，几小时）
REM      run_phase6_download.bat           CESM1-LE 20 成员（~100 GB，1–2 天）
REM
REM  细节与验收标准见：待办.md、docs\阶段计划.md、results\复现报告.md
REM ============================================================================
setlocal
cd /d "%~dp0"
echo [run_all_phases] 工作目录: %CD%
python python\run_phases.py %*
set RC=%ERRORLEVEL%
echo.
echo [run_all_phases] 退出码 = %RC%
if "%1"=="" pause
exit /b %RC%
