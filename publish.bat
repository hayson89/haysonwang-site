@echo off
chcp 65001 >nul
title 发布到 Cloudflare

echo ============================
echo 发布 haysonwang.com 到 CF
echo ============================

echo.
echo [1/3] 同步 08_Website -^> content ...
cd /d E:\Website\quartz
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0sync-content.ps1" -NoPause
if errorlevel 1 (
  echo 内容同步失败，已取消发布。
  pause
  exit /b 1
)

echo.
echo [2/3] 提交 08_Website 源头仓库（本地存档）...
cd /d E:\ObsidianVault\08_Website
git add -A
git commit -m "update source %date%"
if errorlevel 1 echo （08_Website 无变更或提交跳过，继续）

echo.
echo [3/3] 推送 quartz 仓库到 GitHub / Cloudflare ...
cd /d E:\Website\quartz
git add -A
git commit -m "update website"
git push
if errorlevel 1 (
  echo 推送失败，请检查网络后重试。
  pause
  exit /b 1
)

echo.
echo ============================
echo 发布完成！Cloudflare 构建完成后（约 1-2 分钟）网站生效。
echo ============================

pause
