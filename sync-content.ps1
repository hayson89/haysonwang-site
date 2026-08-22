[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$sourceRoot = "E:\ObsidianVault\08_Website"
$contentRoot = Join-Path $PSScriptRoot "content"

# Obsidian is the source of truth. The Chinese folders are intentionally
# mapped to the existing Quartz routes, so published URLs remain unchanged.
$folderMappings = @(
  @{ Source = "甲病专题"; Destination = "Nail_Disorders" },
  @{ Source = "健康教育"; Destination = "Medical_Education" },
  @{ Source = "临床实践"; Destination = "Clinical_Practice" },
  @{ Source = "医学研究"; Destination = "Medical_Research" },
  @{ Source = "图片"; Destination = "image" },
  @{ Source = "assets"; Destination = "assets" }
)

$fileMappings = @(
  @{ Source = "关于我.md"; Destination = "About_Me.md" },
  @{ Source = "目录.md"; Destination = "index.md" }
)

if (-not (Test-Path -LiteralPath $sourceRoot -PathType Container)) {
  throw "Obsidian source folder does not exist: $sourceRoot"
}

New-Item -ItemType Directory -Path $contentRoot -Force | Out-Null

function Copy-ChangedFile([string]$source, [string]$destination) {
  if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
    Write-Warning "Skipped missing source file: $source"
    return
  }

  $changed = -not (Test-Path -LiteralPath $destination -PathType Leaf)
  if (-not $changed) {
    $changed = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne
      (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash
  }

  if ($changed) {
    Copy-Item -LiteralPath $source -Destination $destination -Force
    Write-Host "Updated file: $($source | Split-Path -Leaf)"
  }
}

foreach ($mapping in $fileMappings) {
  Copy-ChangedFile (Join-Path $sourceRoot $mapping.Source) (Join-Path $contentRoot $mapping.Destination)
}

foreach ($mapping in $folderMappings) {
  $source = Join-Path $sourceRoot $mapping.Source
  $destination = Join-Path $contentRoot $mapping.Destination
  if (-not (Test-Path -LiteralPath $source -PathType Container)) {
    Write-Warning "Skipped missing source folder: $source"
    continue
  }

  New-Item -ItemType Directory -Path $destination -Force | Out-Null
  & robocopy $source $destination /E /COPY:DAT /DCOPY:DAT /FFT /XJ /R:2 /W:1 /XD ".obsidian" ".git" ".trash" /XF ".DS_Store" "Thumbs.db" "*.tmp"
  $robocopyExitCode = $LASTEXITCODE
  if ($robocopyExitCode -ge 8) {
    throw "Sync failed for '$($mapping.Source)' (Robocopy exit code: $robocopyExitCode)."
  }
}

Write-Host "Content sync completed. No Quartz-only files were deleted."
