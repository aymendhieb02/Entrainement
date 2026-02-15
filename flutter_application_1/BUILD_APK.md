# Build & run APK (pose model in release)

## Flutter not recognized in terminal

Flutter is installed at **`C:\Users\Msi\flutter\bin`** but not in your PATH.

**Option A – Use the script (recommended)**  
In PowerShell, from this folder:
```powershell
.\run_flutter.ps1
```
This adds Flutter to PATH for that session and runs the app in Chrome.

**Option B – Add Flutter to PATH permanently**  
1. Windows: Paramètres > Système > À propos > Paramètres système avancés > Variables d’environnement.  
2. Sous "Variables utilisateur", sélectionnez `Path` > Modifier > Nouveau.  
3. Ajoutez : `C:\Users\Msi\flutter\bin`.  
4. Fermez et rouvrez le terminal, puis : `flutter run --release -d chrome`.

**Option C – Use full path in this terminal**  
```powershell
$env:Path = "C:\Users\Msi\flutter\bin;" + $env:Path
flutter run --release -d chrome
```

## Build APK (Android)

You need the **Android SDK** (e.g. via [Android Studio](https://developer.android.com/studio)).  
Then set **ANDROID_HOME** (e.g. `C:\Users\<you>\AppData\Local\Android\Sdk`) in Variables d’environnement.  
After that, in a terminal where `flutter` works:
```bash
flutter build apk --release
```
APK path: `build\app\outputs\flutter-apk\app-release.apk`.

---

## Why the model didn't work in APK before

- **Camera permission** was missing in `AndroidManifest.xml` for release.
- **InputImage format**: On Android release, the camera often gives YUV_420_888 (3 planes). ML Kit expects **NV21**. Concatenating the 3 planes is wrong; the code now converts YUV420 → NV21 so the pose model receives valid input.
- **Feedback**: The UI now shows "Model: starting...", "Pose: point camera at body", or "Pose: OK" so you can see that the model is running.

## Build release APK

From the project root (`flutter_application_1`):

```bash
flutter pub get
flutter build apk --release
```

APK output:

- `build/app/outputs/flutter-apk/app-release.apk`

## Run on device / emulator

```bash
flutter run --release
```

Or install the APK manually on a device and open the app. Grant **Camera** when prompted.

## Assets

- `assets/complete_exercise_biomechanics_database.json` is included (from the guide).
- The app uses **Google ML Kit** pose detection (built-in model), not the `.task` file. The `.task` file in the guide is for reference; ML Kit bundles its own model and works offline in the APK.
