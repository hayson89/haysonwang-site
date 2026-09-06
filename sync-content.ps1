# ============================================================
# sync-content.ps1 — 统一同步入口（2026-09-06）
# 职责：调用 sync-website.py 引擎完成
#   1. 规范化 08_Website（图片名 slug 化、引用改相对路径、
#      htm 链接修正、清理脚本残留；从 05_Research 复制来的
#      内容路径不规范会被自动修好）
#   2. robocopy /MIR 镜像 08_Website -> quartz/content
#
# 用法：
#   双击 / 右键运行                规范化 + 镜像（不上线）
#   .\sync-content.ps1 -dry       演练，不写任何文件
#   .\sync-content.ps1 -build     同步后本地构建验证
# 流程位置：手动复制到 08_Website -> 本脚本 -> preview.bat 预览
#           -> publish.bat 推送上线
# ============================================================
param([switch]$NoPause)

$python = "C:\Users\Hayson\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
$script = Join-Path $PSScriptRoot "sync-website.py"

Write-Host "同步 08_Website -> quartz/content ..." -ForegroundColor Cyan
& $python $script @args
$code = $LASTEXITCODE

if ($code -ne 0) {
    Write-Host "同步失败 (exit $code)，请检查上方日志" -ForegroundColor Red
} else {
    Write-Host "同步完成" -ForegroundColor Green
}

if (-not $NoPause) { Read-Host "按回车键退出" }
exit $code
