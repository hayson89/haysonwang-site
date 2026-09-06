@echo off
chcp 65001 >nul
title Publish haysonwang.com

echo ============================
echo Publish haysonwang.com
echo ============================
echo.
echo 栏目: 甲病专题 / 健康教育 / 临床实践 / 医学研究
echo 状态: 扁平化目录 + 共享 images/ 文件夹
echo ============================

echo.
echo [1/3] Syncing website content...
cd /d E:\Website\quartz

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0sync-content.ps1" -NoPause

if errorlevel 1 (
    echo.
    echo ERROR: Content sync failed.
    pause
    exit /b 1
)

echo.
echo [2/3] Committing source repository...
cd /d E:\ObsidianVault\08_Website

git add -A
git diff --cached --quiet

if errorlevel 1 (
    git commit -m "update source"
    if errorlevel 1 (
        echo.
        echo ERROR: Source commit failed.
        pause
        exit /b 1
    )
) else (
    echo No source changes.
)

echo.
echo [3/3] Pushing Quartz repository...
cd /d E:\Website\quartz

git add -A
git diff --cached --quiet

if errorlevel 1 (
    git commit -m "update website"
    if errorlevel 1 (
        echo.
        echo ERROR: Website commit failed.
        pause
        exit /b 1
    )
) else (
    echo No website changes.
)

git push

if errorlevel 1 (
    echo.
    echo ERROR: GitHub push failed.
    pause
    exit /b 1
)

echo.
echo ============================
echo Publish completed.
echo ============================
echo.

pause