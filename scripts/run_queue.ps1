param(
  [Parameter(Mandatory = $true)][string]$Ids,
  [Parameter(Mandatory = $true)][string]$Log,
  [int]$SleepSec = 6,
  [switch]$Force
)
# 串行执行一组任务。上游代理有并发缓冲上限，这里固定单进程串行 + 间隔。
$ErrorActionPreference = 'Continue'
Remove-Item Env:OPENAI_BASE_URL, Env:OPENAI_API_KEY -ErrorAction SilentlyContinue
$here = $PSScriptRoot
$root = Split-Path $here -Parent
$ok = @(); $fail = @(); $skip = @()
foreach ($raw in ($Ids -split ',')) {
  $id = $raw.Trim()
  if (-not $id) { continue }
  $rec = Join-Path $root "00_生成记录\$id.json"
  if (-not $Force -and (Test-Path $rec)) {
    $status = (Get-Content $rec -Raw -Encoding UTF8 | ConvertFrom-Json).status
    if ($status -eq 'success') {
      Add-Content -Path $Log -Encoding utf8 -Value "[$(Get-Date -Format o)] SKIP(success) $id"
      $skip += $id
      continue
    }
  }
  Add-Content -Path $Log -Encoding utf8 -Value "[$(Get-Date -Format o)] START $id"
  $out = & python "$here\render_asset.py" $id 2>&1
  $code = $LASTEXITCODE
  Add-Content -Path $Log -Encoding utf8 -Value ("$out" -join "`n")
  if ($code -eq 0) { $ok += $id } else { $fail += $id }
  Add-Content -Path $Log -Encoding utf8 -Value "[$(Get-Date -Format o)] END $id exit=$code"
  if ($SleepSec -gt 0) { Start-Sleep -Seconds $SleepSec }
}
Add-Content -Path $Log -Encoding utf8 -Value "SUMMARY ok=$($ok -join ';') fail=$($fail -join ';') skip=$($skip -join ';')"
Write-Output "SUMMARY ok=$($ok -join ';') fail=$($fail -join ';') skip=$($skip -join ';')"
