# Set ANDROID_HOME and build APK (run after installing Android Studio / SDK)
$sdkPath = "$env:LOCALAPPDATA\Android\Sdk"
if (-not (Test-Path $sdkPath)) {
    $sdkPath = "$env:USERPROFILE\AppData\Local\Android\Sdk"
}
if (-not (Test-Path $sdkPath)) {
    Write-Host "Android SDK not found at default location." -ForegroundColor Red
    Write-Host "Install Android Studio from https://developer.android.com/studio" -ForegroundColor Yellow
    Write-Host "Then set ANDROID_HOME in Environment Variables to your SDK path." -ForegroundColor Yellow
    Write-Host "See ANDROID_SDK_SETUP.md for details."
    exit 1
}

$env:ANDROID_HOME = $sdkPath
$env:Path = "$sdkPath\platform-tools;$sdkPath\emulator;$env:Path"
Write-Host "ANDROID_HOME = $sdkPath" -ForegroundColor Green
flutter build apk --release
