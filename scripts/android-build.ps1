param([string]$JdkHome)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
if (-not $JdkHome) {
  if (Test-Path -LiteralPath 'D:\JAVA21\bin\java.exe') { $JdkHome = 'D:\JAVA21' } else { $JdkHome = $env:JAVA_HOME }
}
if (-not $JdkHome -or -not (Test-Path -LiteralPath (Join-Path $JdkHome 'bin\java.exe'))) { throw 'Java 21 is required; pass -JdkHome with its installation directory.' }
$env:JAVA_HOME = $JdkHome
if (-not $env:ANDROID_HOME) { $env:ANDROID_HOME = Join-Path (Get-Location) '.tooling\android-sdk' }
if (-not (Test-Path -LiteralPath (Join-Path $env:ANDROID_HOME 'platforms\android-35\android.jar'))) {
  throw 'Android SDK 35 is missing. Install it with Android Studio or sdkmanager.'
}
npm run build
if ($LASTEXITCODE -ne 0) { throw 'Web build failed' }
npx cap sync android
if ($LASTEXITCODE -ne 0) { throw 'Capacitor sync failed' }
node scripts/prepare_android.mjs
Push-Location -LiteralPath android
try {
  $localGradle = Join-Path (Split-Path -Parent $PSScriptRoot) '.tooling\gradle-8.11.1\bin\gradle.bat'
  if (Test-Path -LiteralPath $localGradle) { & $localGradle assembleDebug --no-daemon } else { & .\gradlew.bat assembleDebug --no-daemon }
  if ($LASTEXITCODE -ne 0) { throw 'Android build failed' }
} finally { Pop-Location }
New-Item -ItemType Directory -Path release\android -Force | Out-Null
$clientVersion = (Get-Content -LiteralPath package.json -Raw | ConvertFrom-Json).version
$apkOutput = Join-Path 'release\android' ('DawnBreaker-' + $clientVersion + '-Android.apk')
Copy-Item -LiteralPath android\app\build\outputs\apk\debug\app-debug.apk -Destination $apkOutput
Write-Host ('APK: ' + $apkOutput)
