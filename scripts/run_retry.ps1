param(
  [Parameter(Mandatory = $true)][string]$Log,
  [int]$MaxAttempts = 4,
  [int]$BaseSleep = 25
)
# 串行重跑所有未成功的任务，带指数退避。上游 codex 图片接口间歇性返回 500 EOF，重试即可通过。
$ErrorActionPreference = 'Continue'
Remove-Item Env:OPENAI_BASE_URL, Env:OPENAI_API_KEY -ErrorAction SilentlyContinue
$here = $PSScriptRoot
$root = Split-Path $here -Parent

function Get-Pending {
  $out = @()
  foreach ($f in Get-ChildItem (Join-Path $root '00_生成记录') -Filter '*.json' -File) {
    $d = Get-Content $f.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($d.status -ne 'success') { $out += $d.id }
  }
  # 补齐尚未建立记录的清单任务
  $m = Get-Content (Join-Path $root '制作清单.json') -Raw -Encoding UTF8 | ConvertFrom-Json
  foreach ($t in $m.tasks) {
    $rec = Join-Path $root "00_生成记录\$t.json"
    if (-not (Test-Path $rec)) { $out += $t }
  }
  return ($out | Select-Object -Unique)
}

$done = @(); $gaveup = @()
for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
  $pending = @(Get-Pending)
  if ($pending.Count -eq 0) { break }
  Add-Content -Path $Log -Encoding utf8 -Value "=== 尝试 $attempt / $MaxAttempts  待办 $($pending.Count): $($pending -join ',') ==="
  foreach ($id in $pending) {
    Add-Content -Path $Log -Encoding utf8 -Value "[$(Get-Date -Format o)] TRY$attempt START $id"
    $out = & python "$here\render_asset.py" $id 2>&1
    $code = $LASTEXITCODE
    Add-Content -Path $Log -Encoding utf8 -Value ("$out" -join "`n")
    Add-Content -Path $Log -Encoding utf8 -Value "[$(Get-Date -Format o)] TRY$attempt END $id exit=$code"
    if ($code -eq 0) { $done += $id }
    Start-Sleep -Seconds 8
  }
  if ((@(Get-Pending)).Count -gt 0) {
    $wait = $BaseSleep * $attempt
    Add-Content -Path $Log -Encoding utf8 -Value "--- 退避等待 $wait 秒 ---"
    Start-Sleep -Seconds $wait
  }
}
$left = @(Get-Pending)
Add-Content -Path $Log -Encoding utf8 -Value "SUMMARY done=$($done -join ';') remaining=$($left -join ';')"
Write-Output "SUMMARY done=$($done -join ';') remaining=$($left -join ';')"
