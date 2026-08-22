@echo off
chcp 65001 >nul

cd /d E:\Website\quartz

echo ============================
echo 同步 Obsidian 内容
echo ============================

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0sync-content.ps1"
if errorlevel 1 (
  echo 内容同步失败，已取消发布。
  pause
  exit /b 1
)

echo ============================
echo 添加所有网站修改
echo ============================

git add .

echo ============================
echo 提交更新
echo ============================

git commit -m "update website"

echo ============================
echo 推送 GitHub
echo ============================

git push

echo ============================
echo 发布完成
echo ============================

pause
