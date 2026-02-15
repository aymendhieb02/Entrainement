# Script pour définir les variables d'environnement de façon PERMANENTE
# Exécuter en tant qu'administrateur si nécessaire

Write-Host "Configuration des variables d'environnement..." -ForegroundColor Cyan

# Chemin Flutter
$flutterPath = "C:\Users\Msi\flutter\bin"
if (-not (Test-Path $flutterPath)) {
    Write-Host "ERREUR: Flutter non trouvé à $flutterPath" -ForegroundColor Red
    exit 1
}

# Chemin Android SDK (à adapter si différent)
$androidSdkPath = "$env:LOCALAPPDATA\Android\Sdk"
if (-not (Test-Path $androidSdkPath)) {
    $androidSdkPath = "$env:USERPROFILE\AppData\Local\Android\Sdk"
    if (-not (Test-Path $androidSdkPath)) {
        Write-Host "ATTENTION: Android SDK non trouvé. Installez Android Studio d'abord." -ForegroundColor Yellow
        Write-Host "Après installation, modifiez ce script avec le bon chemin SDK." -ForegroundColor Yellow
        $androidSdkPath = Read-Host "Entrez le chemin du SDK Android (ou laissez vide pour ignorer)"
    }
}

# Ajouter Flutter au PATH utilisateur
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$flutterPath*") {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$flutterPath", "User")
    Write-Host "✓ Flutter ajouté au PATH utilisateur" -ForegroundColor Green
} else {
    Write-Host "✓ Flutter déjà dans PATH" -ForegroundColor Green
}

# Définir ANDROID_HOME si SDK trouvé
if ($androidSdkPath -and (Test-Path $androidSdkPath)) {
    [Environment]::SetEnvironmentVariable("ANDROID_HOME", $androidSdkPath, "User")
    Write-Host "✓ ANDROID_HOME = $androidSdkPath" -ForegroundColor Green
    
    # Ajouter platform-tools et emulator au PATH
    $platformTools = "$androidSdkPath\platform-tools"
    $emulator = "$androidSdkPath\emulator"
    $newPath = $userPath
    if ($platformTools -and (Test-Path $platformTools) -and $userPath -notlike "*$platformTools*") {
        $newPath = "$newPath;$platformTools"
    }
    if ($emulator -and (Test-Path $emulator) -and $newPath -notlike "*$emulator*") {
        $newPath = "$newPath;$emulator"
    }
    if ($newPath -ne $userPath) {
        [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
        Write-Host "✓ Android SDK tools ajoutés au PATH" -ForegroundColor Green
    }
} else {
    Write-Host "⚠ ANDROID_HOME non défini (SDK non trouvé)" -ForegroundColor Yellow
}

Write-Host "`n✓ Configuration terminée!" -ForegroundColor Green
Write-Host "Fermez et rouvrez votre terminal pour que les changements prennent effet." -ForegroundColor Yellow
Write-Host "`nVérification:" -ForegroundColor Cyan
Write-Host "  flutter --version"
Write-Host "  echo `$env:ANDROID_HOME"
