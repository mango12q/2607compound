@echo off
chcp 65001 >nul
setlocal
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1

rem ============================================================
rem  把 ERA5 逐月 d2m（netCDF-4 / chunked / zlib）合并成
rem  GrADS sdfopen 能直接打开的年度文件（classic netCDF-3，无压缩无分块）
rem
rem  产物：%~dp0..\d2m_yearly\d2m.era5.daily.YYYY.nc  ~1.4 GB/年
rem  用法：双击本文件 → 全量 1979-2026
rem        带年份参数：run_make_yearly_d2m.bat 2000-2004
rem ============================================================

cd /d "%~dp0"

set YEARS=1979-2026
if not "%~1"=="" set YEARS=%~1

echo [1/2] 生成年度文件：年份 = %YEARS%
python python\make_yearly_d2m.py --years %YEARS% --out "E:\2607compound\data\ERA5\d2m_yearly"
if errorlevel 1 goto fail

echo.
echo [2/2] 回读体检
python python\make_yearly_d2m.py --check-only --out "E:\2607compound\data\ERA5\d2m_yearly"
if errorlevel 1 goto fail

echo.
echo 全部完成。把这些文件拷到 GrADS 机器上，sdfopen 即可。
pause
exit /b 0

:fail
echo.
echo *** 有文件生成或体检失败，见上面的日志 ***
pause
exit /b 1
