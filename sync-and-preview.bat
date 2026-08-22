@echo off
chcp 65001 >nul
title Obsidian - Quartz Preview

cd /d E:\Website\quartz

echo.
echo ==========================================
echo   Obsidian -> Quartz/content -> Preview
echo ==========================================
echo.

echo [1/2] 正在同步 Obsidian 内容...
powershell -ExecutionPolicy Bypass -File ".\sync-content.ps1"

if errorlevel 1 (
    echo.
    echo [错误] 同步失败，请检查上面的提示。
    pause
    exit /b 1
)

echo.
echo [2/2] 正在启动 Quartz Preview...
echo.
echo 浏览器访问：
echo http://localhost:8080
echo.
echo 按 Ctrl+C 可以停止 Preview。
echo.

call npx quartz build --serve

pause