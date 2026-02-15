# Add Flutter to PATH for this session so "flutter" is recognized
$env:Path = "C:\Users\Msi\flutter\bin;" + $env:Path

Write-Host ""
Write-Host "Flutter is now in PATH for this terminal." -ForegroundColor Green
Write-Host ""
Write-Host "Use one of these:" -ForegroundColor Cyan
Write-Host "  flutter run --release -d chrome     (run in Chrome)"
Write-Host "  flutter run --release -d <deviceId> (Android: connect phone/emulator, then flutter devices)"
Write-Host "  flutter build apk --release         (build APK; needs ANDROID_HOME set to Android SDK)"
Write-Host ""
Write-Host "To add Flutter to PATH permanently: Windows Settings > System > About > Advanced system settings > Environment Variables > Path > New > C:\Users\Msi\flutter\bin" -ForegroundColor Yellow
Write-Host ""

# Uncomment one of the following to run:
# flutter run --release -d chrome
# flutter run --release -d windows   # requires Developer Mode for plugins
# flutter run --release             # use when only one device (e.g. Android) is connected
Write-Host "Run: flutter run --release -d chrome" -ForegroundColor Cyan
flutter run --release -d chrome
