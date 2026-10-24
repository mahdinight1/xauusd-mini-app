$ErrorActionPreference = 'Stop'

if (-not (Get-Command flutter -ErrorAction SilentlyContinue)) {
  Write-Error 'Flutter SDK was not found. Install Flutter and Android Studio, then reopen this terminal.'
}

flutter doctor
flutter create --platforms=android --org com.nextrade --project-name nextrade .
$gradlePath = $null
if (Test-Path 'android/app/build.gradle.kts') { $gradlePath = 'android/app/build.gradle.kts' }
elseif (Test-Path 'android/app/build.gradle') { $gradlePath = 'android/app/build.gradle' }
if (-not $gradlePath) { throw 'Flutter scaffold did not create android/app/build.gradle(.kts).' }
$gradle = Get-Content $gradlePath -Raw
if ($gradlePath.EndsWith('.kts')) {
  $updated = [regex]::Replace($gradle, '(?m)^\s*minSdk\s*=\s*(flutter\.minSdkVersion|[0-9]+)', '        minSdk = 24', 1)
  if ($updated -eq $gradle -and $gradle -notmatch '(?m)^\s*minSdk\s*=\s*24') { throw "Could not safely set Android minSdk 24 in $gradlePath" }
} else {
  $updated = [regex]::Replace($gradle, '(?m)^\s*minSdkVersion\s+(flutter\.minSdkVersion|[0-9]+)', '        minSdkVersion 24', 1)
  if ($updated -eq $gradle -and $gradle -notmatch '(?m)^\s*minSdkVersion\s+24') { throw "Could not safely set Android minSdk 24 in $gradlePath" }
}
Set-Content -Path $gradlePath -Value $updated -Encoding utf8
Write-Host "Configured Android minSdk 24 in $gradlePath"
$manifestPath = 'android/app/src/main/AndroidManifest.xml'
if (Test-Path $manifestPath) {
  $manifest = Get-Content $manifestPath -Raw
  if ($manifest -notmatch 'android.permission.INTERNET') {
    $replacement = '    <uses-permission android:name="android.permission.INTERNET" />' + [Environment]::NewLine + '    <application'
    $manifest = [regex]::Replace($manifest, '(?m)^\s*<application', $replacement, 1)
    Set-Content -Path $manifestPath -Value $manifest -Encoding utf8
  }
}
New-Item -ItemType Directory -Force -Path 'android/app/src/debug' | Out-Null
@'
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <application android:usesCleartextTraffic="true" />
</manifest>
'@ | Set-Content -Path 'android/app/src/debug/AndroidManifest.xml' -Encoding utf8
flutter pub get
flutter analyze
flutter test
Write-Host ''
Write-Host 'Android scaffold is ready. Build a release APK with:'
Write-Host 'flutter build apk --release'
