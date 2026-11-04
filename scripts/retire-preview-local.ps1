$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$stableVersion = (Get-Content -LiteralPath (Join-Path $taskRoot 'package.json') -Raw | ConvertFrom-Json).version
if ($stableVersion -ne '1.0.0') { throw 'This cleanup is scoped to the formal 1.0.0 release.' }
foreach ($platform in @('windows','android')) {
  $folder = if ($platform -eq 'windows') { 'desktop' } else { 'android' }
  $envelope = Get-Content -LiteralPath (Join-Path $taskRoot "release/$platform-1.0.0.json") -Raw | ConvertFrom-Json
  $payload = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($envelope.signed)) | ConvertFrom-Json
  $binary = Join-Path $taskRoot "release/$folder/$($payload.filename)"
  if ($payload.version -ne '1.0.0' -or $payload.version_code -ne 7 -or $payload.channel -ne 'stable') { throw 'Stable manifest is not ready.' }
  if ((Get-FileHash -LiteralPath $binary -Algorithm SHA256).Hash.ToLowerInvariant() -ne $payload.sha256) { throw 'Stable binary does not match its manifest.' }
}
$targets = @()
foreach ($folder in @('release/desktop','release/android')) {
  $targets += Get-ChildItem -LiteralPath (Join-Path $taskRoot $folder) -File | Where-Object { $_.Name -match '^DawnBreaker-(\d+\.\d+\.\d+)-(Windows\.exe|Android\.apk)$' -and $Matches[1] -ne '1.0.0' }
}
$targets += Get-ChildItem -LiteralPath (Join-Path $taskRoot 'release') -File | Where-Object { $_.Name -match '^(windows|android)-(\d+\.\d+\.\d+)\.json$' -and $Matches[2] -ne '1.0.0' }
$targets += Get-ChildItem -LiteralPath (Join-Path $taskRoot 'release-notes') -File | Where-Object { $_.Name -match '^\d+\.\d+\.\d+\.md$' -and $_.Name -ne '1.0.0.md' }
foreach ($name in @('artifacts/dawnbreaker-server.tar.gz','artifacts/resources-1.2.0.tar.gz')) {
  $file = Join-Path $taskRoot $name
  if (Test-Path -LiteralPath $file -PathType Leaf) { $targets += Get-Item -LiteralPath $file }
}
$allowedParents = @('release/desktop','release/android','release','release-notes','artifacts') | ForEach-Object { (Resolve-Path -LiteralPath (Join-Path $taskRoot $_)).Path }
foreach ($file in $targets) {
  $resolved = (Resolve-Path -LiteralPath $file.FullName).Path
  if (-not $resolved.StartsWith($taskRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -or (Split-Path -Parent $resolved) -notin $allowedParents -or $file.LinkType) { throw "Unexpected cleanup path: $resolved" }
}
foreach ($file in $targets) {
  Remove-Item -LiteralPath $file.FullName -Force
  Write-Output ('Removed ' + $file.Name)
}
