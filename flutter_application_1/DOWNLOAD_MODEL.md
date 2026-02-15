# Télécharger le modèle MediaPipe Pose Landmarker

Pour que l'app fonctionne avec MediaPipe, vous devez télécharger le fichier `.task` :

1. **Télécharger le modèle** :
   - URL: https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task
   - Ou: https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/latest/pose_landmarker_heavy.task (plus précis mais plus lent)

2. **Placer le fichier** :
   - Copiez `pose_landmarker_lite.task` dans : `flutter_application_1/assets/models/`

3. **Vérifier** :
   - Le fichier doit être à : `assets/models/pose_landmarker_lite.task`
   - Le `pubspec.yaml` doit déjà référencer ce fichier dans `assets:`

Après avoir ajouté le fichier, relancez `flutter pub get` et `flutter run`.
