$source = "E:\ObsidianVault\08_Website"
$destination = "E:\Website\quartz\content"

Write-Host "开始同步 Obsidian Website..."

robocopy `
$source `
$destination `
/MIR `
/XD .obsidian .git `
/XF *.canvas workspace.json

Write-Host "同步完成"
pause