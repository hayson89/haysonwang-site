# ============================================================
# 统一发布入口（2026-09-05 起取代旧的 robocopy 直镜像流程）
# 实际逻辑全部在 sync-research.py 中：
#   1. 05_Research -> 08_Website/research 变换（图片小写化、
#      相对路径改写、htm 链接修正、清理脚本残留）
#   2. 08_Website -> content 镜像（robocopy /MIR）
#   3. 运行 publish.py（frontmatter publish: true 的笔记）
#
# 用法：
#   双击本文件 / .\sync-content.ps1        完整同步（默认，不推送）
#   .\sync-content.ps1 -dry                演练模式，不写任何文件
#   .\sync-content.ps1 -build              同步后本地构建 public/
#   .\sync-content.ps1 -push               同步后 git 提交并推送上线
#   （-push 与 -build 可同时使用）
# ============================================================

$python = "C:\Users\Hayson\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
$script = Join-Path $PSScriptRoot "sync-research.py"

Write-Host "统一同步: 05_Research -> 08_Website -> content -> publish ..." -ForegroundColor Cyan
& $python $script @args
$code = $LASTEXITCODE

if ($code -ne 0) {
    Write-Host "同步失败 (exit $code)，请检查上方日志" -ForegroundColor Red
} else {
    Write-Host "同步完成" -ForegroundColor Green
}

Read-Host "按回车键退出"
exit $code
