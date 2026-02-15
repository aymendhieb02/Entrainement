# 🚀 Démarrage Rapide - Google ML Kit

## Étape 1 : Variables d'environnement (UNE SEULE FOIS)

```powershell
cd C:\Users\Msi\OneDrive\Bureau\jawher\entrainement\flutter_application_1
.\set_env_permanent.ps1
```

**Fermer et rouvrir le terminal** après.

---

## Étape 2 : Installer les dépendances

```powershell
cd C:\Users\Msi\OneDrive\Bureau\jawher\entrainement\flutter_application_1
flutter pub get
```

---

## Étape 3 : Lancer sur Android

```powershell
# Vérifier le téléphone connecté
flutter devices

# Lancer (remplacez <deviceId> par l'ID de votre téléphone)
flutter run --release -d <deviceId>
```

**Exemple** :
```powershell
flutter run --release -d emulator-5554
```

---

## Étape 4 : Exporter l'APK

```powershell
flutter build apk --release
```

**APK** : `build\app\outputs\flutter-apk\app-release.apk`

---

## ✅ Vérifications que ça fonctionne

Sur le téléphone, vous devriez voir :

1. **Caméra s'ouvre** ✅
2. **Overlay en haut** avec :
   - REPS (compteur)
   - ANGLE (angle du coude)
   - FEEDBACK (EXCELLENT / NEEDS IMPROVEMENT)
3. **Texte en bas** :
   - "Model: starting..." → "Pose: OK (X frames)" quand vous bougez
4. **Les reps s'incrémentent** quand vous faites l'exercice correctement

---

## 🐛 Si problème

- **"flutter n'est pas reconnu"** → Relancer `set_env_permanent.ps1`
- **"No Android SDK"** → Installer Android Studio
- **Caméra ne s'ouvre pas** → Vérifier permissions dans Paramètres Android
- **Pas de pose détectée** → Vérifier que vous êtes bien dans le champ de la caméra

Voir `ML_KIT_SETUP.md` pour plus de détails.
