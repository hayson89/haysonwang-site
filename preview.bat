@echo off
chcp 65001 >nul
title Quartz 本地预览

echo ============================
echo Quartz 本地预览启动
echo ============================
echo.
echo 栏目: 甲病专题 / 健康教育 / 临床实践 / 医学研究
echo 状态: 扁平化目录 + 共享 images/ 文件夹
echo.
echo （仅本机预览，不上线；发布请用 publish.bat）
echo ============================

cd /d E:\Website\quartz

echo.
echo [1/2] 正在同步 08_Website -^> content ...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0sync-content.ps1" -NoPause
if errorlevel 1 (
  echo 内容同步失败，已取消预览。
  pause
  exit /b 1
)

echo.
echo [2/2] 正在启动 Quartz...
echo 浏览器访问:
echo http://localhost:8080
echo （按 Ctrl+C 停止预览）
echo.

npx quartz build --serve

pause
