@echo off
chcp 65001 >nul
title CESM1-LE download - live monitor
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\2607compound\show_cesm_progress.ps1"
pause
