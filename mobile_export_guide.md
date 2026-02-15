# Mobile Export Guide - Flutter & TFLite Integration

## Overview
This guide explains how to adapt the Python biomechanics coach application to Flutter/mobile using MediaPipe and TFLite.

## Understanding the Architecture

### Current Python Stack
1. **Pose Estimation**: MediaPipe Pose (uses TFLite models internally)
2. **Logic Layer**: `BiomechanicsCoach` class (angle calculations, rep counting, form validation)
3. **Database**: `complete_exercise_biomechanics_database.json`

### Mobile Strategy

> **Important**: We don't "convert Python to TFLite". Instead, we use MediaPipe's existing TFLite models and port the logic to Dart.

## Step 1: MediaPipe in Flutter

### Option A: MediaPipe Flutter Plugin (Recommended)
```yaml
# pubspec.yaml
dependencies:
  google_ml_kit: ^0.16.0  # Includes pose detection
```

### Option B: TFLite Directly
```yaml
dependencies:
  tflite_flutter: ^0.10.0
```

Download the MediaPipe Pose model:
- **Model**: [pose_landmark_lite.tflite](https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task)
- **Place in**: `assets/models/`

## Step 2: Port BiomechanicsCoach to Dart

### Dart Implementation Example

```dart
import 'dart:math';
import 'package:flutter/services.dart' show rootBundle;
import 'dart:convert';

class BiomechanicsCoach {
  late Map<String, dynamic> db;
  late Map<String, dynamic> exInfo;
  late Map<String, dynamic> template;
  late Map<String, dynamic> viewCfg;
  
  int reps = 0;
  String stage = "extended";
  double currentAngle = 180.0;
  String feedback = "EXCELLENT";
  String formIssue = "";
  
  List<bool> smoothingBuffer = [];
  final int maxBufferSize = 20;
  double lastBadFormTime = 0;
  final double warningDuration = 1.5;

  Future<void> initialize(String exerciseKey) async {
    // Load JSON database
    String jsonString = await rootBundle.loadString(
      'assets/complete_exercise_biomechanics_database.json'
    );
    db = json.decode(jsonString);
    
    exInfo = db['exercises'][exerciseKey];
    template = db['base_templates'][exInfo['uses_template']];
    viewCfg = template['views']['side'];
  }

  double calculateAngle(Map<String, double> a, Map<String, double> b, Map<String, double> c) {
    double baX = a['x']! - b['x']!;
    double baY = a['y']! - b['y']!;
    double bcX = c['x']! - b['x']!;
    double bcY = c['y']! - b['y']!;
    
    double dotProduct = baX * bcX + baY * bcY;
    double magnitudeBA = sqrt(baX * baX + baY * baY);
    double magnitudeBC = sqrt(bcX * bcX + bcY * bcY);
    
    double cosineAngle = dotProduct / (magnitudeBA * magnitudeBC);
    cosineAngle = cosineAngle.clamp(-1.0, 1.0);
    
    return acos(cosineAngle) * 180 / pi;
  }

  int processForm(Map<String, Map<String, double>> landmarks, double currentTimestamp) {
    // Determine which side is visible
    String side = landmarks['leftelbow']!['vis']! > landmarks['rightelbow']!['vis']! 
        ? "left" 
        : "right";
    
    bool frameIsExcellent = true;
    List<String> currentIssues = [];

    // Process each joint
    viewCfg.forEach((jointName, cfg) {
      Map<String, List<String>> ptsMap = {
        'elbow': ['${side}shoulder', '${side}elbow', '${side}wrist'],
        'shoulder': ['${side}hip', '${side}shoulder', '${side}elbow'],
        'hip': ['${side}shoulder', '${side}hip', '${side}knee']
      };

      if (!ptsMap.containsKey(jointName)) return;

      List<Map<String, double>> pts = ptsMap[jointName]!
          .map((p) => landmarks[p]!)
          .toList();

      double angle = calculateAngle(pts[0], pts[1], pts[2]);

      if (cfg['type'] == 'primary') {
        currentAngle = angle;
      } else if (cfg['type'] == 'stability') {
        if ((angle - cfg['target']).abs() > cfg['max_deviation']) {
          frameIsExcellent = false;
          currentIssues.add("STABILIZE ${jointName.toUpperCase()}");
        }
      }
    });

    // Update smoothing buffer
    smoothingBuffer.add(frameIsExcellent);
    if (smoothingBuffer.length > maxBufferSize) {
      smoothingBuffer.removeAt(0);
    }

    // Check if bad form
    int badFrameCount = smoothingBuffer.where((x) => !x).length;
    if (badFrameCount > (maxBufferSize * 0.3)) {
      lastBadFormTime = currentTimestamp;
      if (currentIssues.isNotEmpty) formIssue = currentIssues[0];
    }

    // Determine feedback
    if ((currentTimestamp - lastBadFormTime) < warningDuration) {
      feedback = "NEEDS IMPROVEMENT";
    } else {
      feedback = "EXCELLENT";
      formIssue = "";
    }

    // Rep counter
    double flexedTarget = viewCfg['elbow']['flexed'].toDouble();
    double extendedTarget = viewCfg['elbow']['extended'].toDouble();

    if (currentAngle <= (flexedTarget + 25)) {
      if (stage == "extended") stage = "flexed";
    }
    if (currentAngle >= (extendedTarget - 25)) {
      if (stage == "flexed") {
        reps++;
        stage = "extended";
      }
    }

    return reps;
  }
}
```

## Step 3: Flutter UI Integration

```dart
import 'package:camera/camera.dart';
import 'package:google_ml_kit/google_ml_kit.dart';

class BiomechanicsScreen extends StatefulWidget {
  @override
  _BiomechanicsScreenState createState() => _BiomechanicsScreenState();
}

class _BiomechanicsScreenState extends State<BiomechanicsScreen> {
  late CameraController _cameraController;
  final PoseDetector _poseDetector = GoogleMlKit.vision.poseDetector();
  final BiomechanicsCoach _coach = BiomechanicsCoach();
  
  @override
  void initState() {
    super.initState();
    _initializeCamera();
    _coach.initialize('BBCurl');
  }

  Future<void> _initializeCamera() async {
    final cameras = await availableCameras();
    _cameraController = CameraController(
      cameras[0],
      ResolutionPreset.high,
      enableAudio: false,
    );
    
    await _cameraController.initialize();
    _cameraController.startImageStream(_processCameraImage);
    setState(() {});
  }

  void _processCameraImage(CameraImage image) async {
    final inputImage = _convertToInputImage(image);
    final poses = await _poseDetector.processImage(inputImage);
    
    if (poses.isNotEmpty) {
      final landmarks = _extractLandmarks(poses.first);
      final timestamp = DateTime.now().millisecondsSinceEpoch / 1000.0;
      
      setState(() {
        _coach.processForm(landmarks, timestamp);
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(
        children: [
          // Camera preview
          CameraPreview(_cameraController),
          
          // Overlay UI
          Positioned(
            top: 50,
            left: 20,
            child: Container(
              padding: EdgeInsets.all(15),
              decoration: BoxDecoration(
                color: Colors.black54,
                borderRadius: BorderRadius.circular(10),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'REPS: ${_coach.reps}',
                    style: TextStyle(color: Colors.white, fontSize: 24),
                  ),
                  Text(
                    _coach.feedback,
                    style: TextStyle(
                      color: _coach.feedback == "EXCELLENT" 
                          ? Colors.green 
                          : Colors.red,
                      fontSize: 18,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
```

## Step 4: Asset Setup

### pubspec.yaml
```yaml
flutter:
  assets:
    - assets/complete_exercise_biomechanics_database.json
    - assets/models/pose_landmarker_lite.task
```

## TFLite Model Export (Optional)

If you need to optimize the MediaPipe model further:

### Using TensorFlow Lite Converter
```python
import tensorflow as tf

# Load MediaPipe model
converter = tf.lite.TFLiteConverter.from_saved_model('pose_landmark_model')

# Quantize to INT8 for smaller size
converter.optimizations = [tf.lite.Optimize.DEFAULT]
converter.target_spec.supported_types = [tf.int8]

# Convert
tflite_model = converter.convert()

# Save
with open('pose_landmark_int8.tflite', 'wb') as f:
    f.write(tflite_model)
```

## Performance Tips

1. **Use INT8 quantization** for 4x smaller model size
2. **Lower camera resolution** (640x480) for faster processing
3. **Skip frames** if needed (process every 2-3 frames)
4. **Use isolates** in Dart for heavy computation

## Summary

✅ **What to do**:
- Use MediaPipe's existing TFLite models
- Port `BiomechanicsCoach` logic to Dart
- Copy `complete_exercise_biomechanics_database.json` to Flutter assets

❌ **What NOT to do**:
- Don't try to "convert Python code to TFLite"
- Don't train a new model (MediaPipe is already optimized)

## Resources

- [MediaPipe Pose](https://developers.google.com/mediapipe/solutions/vision/pose_landmarker)
- [Google ML Kit Flutter](https://pub.dev/packages/google_ml_kit)
- [TFLite Flutter Plugin](https://pub.dev/packages/tflite_flutter)
