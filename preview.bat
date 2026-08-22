@echo off
chcp 65001 >nul

echo ============================
echo Quartz 本地预览启动
echo ============================

cd /d E:\Website\quartz

echo.
echo 正在同步 Obsidian 内容...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0sync-content.ps1"
if errorlevel 1 (
  echo 内容同步失败，已取消预览。
  pause
  exit /b 1
)

echo.
echo 正在启动 Quartz...
echo 浏览器访问:
echo http://localhost:8080
echo.

npx quartz build --serve

pause
