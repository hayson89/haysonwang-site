@echo off
chcp 65001 >nul

echo ============================
echo Quartz 本地预览启动
echo ============================

cd /d E:\Website\quartz

echo.
echo 正在启动 Quartz...
echo 浏览器访问:
echo http://localhost:8080
echo.

npx quartz build --serve

pause