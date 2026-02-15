# Configuration Google ML Kit - Guide Complet

## ✅ Ce qui est configuré

1. **Google ML Kit Pose Detection** : Utilisé pour détecter la pose (33 landmarks)
2. **Mapping des landmarks** : Conversion automatique des noms ML Kit (`leftElbow`) vers format attendu (`leftelbow`)
3. **BiomechanicsCoach** : Compare les angles et compte les répétitions
4. **Gestion d'erreurs** : Messages clairs si la caméra ou le modèle ne fonctionne pas

---

## 🔍 Vérifications avant de lancer

### 1. Variables d'environnement (une seule fois)

```powershell
cd C:\Users\Msi\OneDrive\Bureau\jawher\entrainement\flutter_application_1
.\set_env_permanent.ps1
```

**Fermer et rouvrir le terminal**, puis vérifier :

```powershell
flutter --version          # Doit afficher la version Flutter
echo $env:ANDROID_HOME     # Doit afficher le chemin du SDK Android (si installé)
```

### 2. Dépendances installées

```powershell
cd C:\Users\Msi\OneDrive\Bureau\jawher\entrainement\flutter_application_1
flutter pub get
```

**Vérifier** : Pas d'erreur "could not find package"

### 3. Assets présents

```powershell
Test-Path assets\complete_exercise_biomechanics_database.json
```

**Doit retourner** : `True`

---

## 🚀 Lancer l'app

### Sur Android (téléphone connecté)

```powershell
# 1. Vérifier que le téléphone est connecté
flutter devices

# 2. Lancer en release (meilleures performances)
flutter run --release -d <deviceId>

# Exemple si deviceId = emulator-5554:
flutter run --release -d emulator-5554
```

**Sur le téléphone, vous devriez voir** :
- ✅ Caméra qui s'ouvre
- ✅ Overlay avec REPS, ANGLE, FEEDBACK
- ✅ Texte en bas : "Model: starting..." puis "Pose: OK" quand vous bougez
- ✅ Les reps s'incrémentent quand vous faites l'exercice correctement

### Sur Chrome (test rapide - pas de pose detection)

```powershell
flutter run -d chrome
```

**Note** : Sur web, la caméra s'ouvre mais la pose detection ne fonctionne pas (ML Kit ne supporte pas le web).

---

## 📦 Exporter l'APK

```powershell
flutter build apk --release
```

**APK généré** : `build\app\outputs\flutter-apk\app-release.apk`

**Installer sur téléphone** :
1. Copier l'APK sur le téléphone
2. Ouvrir le fichier APK
3. Autoriser l'installation depuis sources inconnues si demandé
4. Installer

---

## 🐛 Dépannage

### "flutter n'est pas reconnu"
→ Relancer `.\set_env_permanent.ps1` et fermer/rouvrir le terminal

### "No Android SDK found"
→ Installer Android Studio, puis relancer `.\set_env_permanent.ps1`

### "Camera error" sur le téléphone
→ Vérifier que l'app a la permission caméra dans Paramètres Android

### Le modèle ne détecte pas de pose
→ Vérifier dans les logs (debug) :
```powershell
flutter run --release -d <deviceId> --verbose
```
Chercher : "ML Kit detected X landmarks" dans les logs

### Les reps ne s'incrémentent pas
→ Vérifier que :
1. Vous êtes bien dans le champ de la caméra
2. Vous faites l'exercice complet (flexion + extension)
3. Les landmarks essentiels sont détectés (voir logs)

---

## 📊 Comment vérifier que le modèle fonctionne

### Indicateurs visuels dans l'app :
1. **En bas de l'écran** :
   - "Model: starting..." → Le modèle démarre
   - "Point camera at body" → Pas de pose détectée
   - "Pose: OK (X frames)" → ✅ Le modèle détecte la pose !

2. **Overlay en haut** :
   - **REPS** : S'incrémente quand vous complétez un mouvement
   - **ANGLE** : Change en temps réel (ex: 180° → 35° → 180°)
   - **FEEDBACK** : "EXCELLENT" (vert) ou "NEEDS IMPROVEMENT" (orange)

### Logs de debug :
Dans le code, les logs affichent :
- `ML Kit detected X landmarks: leftelbow, rightelbow, ...`
- Erreurs de conversion d'image si problème

---

## ✅ Checklist finale

- [ ] Variables d'environnement définies (`set_env_permanent.ps1`)
- [ ] `flutter pub get` exécuté sans erreur
- [ ] Téléphone connecté (`flutter devices` montre le device)
- [ ] App lancée (`flutter run --release -d <deviceId>`)
- [ ] Caméra s'ouvre et demande permission
- [ ] Overlay apparaît avec REPS/ANGLE/FEEDBACK
- [ ] Texte en bas montre "Pose: OK" quand vous bougez
- [ ] Les reps s'incrémentent lors de l'exercice

Si tout est ✅, **le modèle fonctionne parfaitement** ! 🎉
