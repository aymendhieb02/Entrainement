# Commandes pour lancer l'app

## 1. Définir les variables d'environnement de façon PERMANENTE

**Exécuter une seule fois** (en tant qu'administrateur si nécessaire) :

```powershell
cd C:\Users\Msi\OneDrive\Bureau\jawher\entrainement\flutter_application_1
.\set_env_permanent.ps1
```

Puis **fermer et rouvrir** le terminal.

---

## 2. Télécharger le modèle MediaPipe (une seule fois)

1. Télécharger : https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task
2. Placer dans : `flutter_application_1/assets/models/pose_landmarker_lite.task`

---

## 3. Installer les dépendances

```powershell
cd C:\Users\Msi\OneDrive\Bureau\jawher\entrainement\flutter_application_1
flutter pub get
```

---

## 4. Lancer l'app sur Android (téléphone connecté)

```powershell
# Vérifier que le téléphone est connecté
flutter devices

# Lancer en release
flutter run --release -d <deviceId>
```

**Exemple** :
```powershell
flutter run --release -d emulator-5554
```

---

## 5. Exporter l'APK

```powershell
flutter build apk --release
```

L'APK sera dans : `build\app\outputs\flutter-apk\app-release.apk`

---

## Vérifications

- ✅ Flutter dans PATH : `flutter --version`
- ✅ ANDROID_HOME défini : `echo $env:ANDROID_HOME`
- ✅ Téléphone connecté : `flutter devices`
- ✅ Modèle présent : `Test-Path assets\models\pose_landmarker_lite.task`
