  # Note sur MediaPipe

## Situation actuelle

**Le package `mediapipe_tasks_flutter` n'existe pas sur pub.dev.**

L'app utilise actuellement **Google ML Kit** pour la détection de pose, qui fonctionne bien et fournit des résultats similaires à MediaPipe.

## Pourquoi pas MediaPipe directement ?

Les fichiers `.task` MediaPipe nécessitent le **runtime MediaPipe** complet pour s'exécuter. Ce runtime n'est pas disponible comme package Flutter officiel sur pub.dev.

## Options pour utiliser MediaPipe

### Option 1 : Google ML Kit (actuel - RECOMMANDÉ)
- ✅ Fonctionne immédiatement
- ✅ Pas de configuration supplémentaire
- ✅ Résultats similaires à MediaPipe
- ✅ Supporté officiellement

### Option 2 : Intégration native MediaPipe
Pour utiliser vraiment MediaPipe `.task` :
1. Créer un plugin Flutter natif (Android/iOS)
2. Intégrer MediaPipe C++ SDK
3. Exposer les APIs via MethodChannel
4. Beaucoup plus complexe, nécessite compilation native

### Option 3 : Attendre un package officiel
Google pourrait publier `mediapipe_tasks_flutter` à l'avenir, mais ce n'est pas disponible actuellement.

## Conclusion

**L'app fonctionne avec Google ML Kit** qui détecte la pose et permet à `BiomechanicsCoach` de comparer les angles et compter les répétitions. C'est la solution la plus pratique pour l'instant.

Si vous avez absolument besoin de MediaPipe, il faudra créer une intégration native personnalisée.
