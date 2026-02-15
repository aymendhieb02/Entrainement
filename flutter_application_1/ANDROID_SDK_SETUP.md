# Configurer le SDK Android pour générer l’APK

L’erreur **« No Android SDK found »** signifie que Flutter ne trouve pas le SDK Android. Il faut l’installer puis définir la variable **ANDROID_HOME**.

---

## Option 1 : Installer Android Studio (recommandé)

1. **Télécharger Android Studio**  
   https://developer.android.com/studio  

2. **Installer** en suivant l’assistant. À la fin, l’installateur propose d’installer le **Android SDK** : cochez cette option.

3. **Récupérer le chemin du SDK**  
   Après installation : Android Studio → **File** → **Settings** (ou **More Actions** → **SDK Manager**).  
   En haut, vous voyez **Android SDK Location**, par exemple :  
   `C:\Users\Msi\AppData\Local\Android\Sdk`

4. **Définir ANDROID_HOME** (voir section « Définir ANDROID_HOME » ci‑dessous) avec ce chemin.

---

## Option 2 : Outils en ligne de commande uniquement

Si vous ne voulez pas installer Android Studio :

1. **Télécharger les command-line tools**  
   https://developer.android.com/studio#command-tools  
   (section « Command line tools only »)

2. **Extraire** dans un dossier, par exemple `C:\Android\cmdline-tools\latest`

3. **Ouvrir un terminal** dans ce dossier et lancer :
   ```bash
   bin\sdkmanager --sdk_root=C:\Android "platform-tools" "platforms;android-34" "build-tools;34.0.0"
   ```
   Cela crée le SDK dans `C:\Android`. Utilisez **ANDROID_HOME** = `C:\Android`.

---

## Définir ANDROID_HOME

### Pour la session en cours (temporaire)

Dans **PowerShell** (remplacez le chemin par le vôtre) :

```powershell
$env:ANDROID_HOME = "C:\Users\Msi\AppData\Local\Android\Sdk"
$env:Path = "$env:ANDROID_HOME\platform-tools;$env:ANDROID_HOME\emulator;" + $env:Path
flutter build apk --release
```

### De façon permanente (recommandé)

1. Touche **Windows** → taper **Variables d’environnement** → **Modifier les variables d’environnement système**.
2. **Variables d’environnement** → sous « Variables utilisateur », sélectionner **Path** → **Modifier**.
3. **Nouveau** et ajouter :
   - `C:\Users\Msi\AppData\Local\Android\Sdk\platform-tools`
   - `C:\Users\Msi\AppData\Local\Android\Sdk\emulator`
   (en adaptant si votre SDK est ailleurs).
4. Toujours dans Variables utilisateur, cliquer **Nouvelle** :
   - Nom : `ANDROID_HOME`
   - Valeur : `C:\Users\Msi\AppData\Local\Android\Sdk` (votre chemin SDK).
5. **OK** partout, puis **fermer et rouvrir** le terminal (et Cursor si besoin).

Ensuite, dans le projet :

```powershell
cd C:\Users\Msi\OneDrive\Bureau\jawher\entrainement\flutter_application_1
flutter build apk --release
```

L’APK sera dans : `build\app\outputs\flutter-apk\app-release.apk`.
