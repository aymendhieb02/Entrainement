// Pose detection using Google ML Kit (Android/iOS only).
// Note: MediaPipe Tasks Flutter package doesn't exist on pub.dev.
// For MediaPipe .task files, you'd need native MediaPipe integration.
// Google ML Kit provides similar pose detection capabilities.
import 'dart:typed_data';
import 'dart:ui' show Size;
import 'package:flutter/foundation.dart' show WriteBuffer, kDebugMode, debugPrint;
import 'package:camera/camera.dart';
import 'package:flutter/services.dart' show DeviceOrientation;
import 'package:google_ml_kit/google_ml_kit.dart' show PoseDetector, PoseDetectorOptions, PoseDetectionModel, PoseDetectionMode, GoogleMlKit, Pose, InputImage, InputImageFormat, InputImageFormatValue, InputImageMetadata, InputImageRotation, InputImageRotationValue;

import 'platform_io.dart' if (dart.library.html) 'platform_stub.dart' as io;

final Map<DeviceOrientation, int> _orientations = {
  DeviceOrientation.portraitUp: 0,
  DeviceOrientation.landscapeLeft: 90,
  DeviceOrientation.portraitDown: 180,
  DeviceOrientation.landscapeRight: 270,
};

PoseDetector createPoseDetector() {
  return GoogleMlKit.vision.poseDetector(
    poseDetectorOptions: PoseDetectorOptions(
      model: PoseDetectionModel.base,
      mode: PoseDetectionMode.stream,
    ),
  );
}

void closePoseDetector(Object? detector) {
  (detector as PoseDetector?)?.close();
}

/// Process a camera frame and return landmarks map for BiomechanicsCoach.
Future<Map<String, Map<String, double>>?> processFrame(
  CameraImage image,
  Object? detector,
  CameraController controller,
) async {
  if (detector == null || detector is! PoseDetector) return null;
  
  try {
    final inputImage = _convertToInputImage(image, controller);
    if (inputImage == null) {
      if (kDebugMode) debugPrint('Failed to convert CameraImage to InputImage');
      return null;
    }
    
    final poses = await detector.processImage(inputImage);
    if (poses.isEmpty) return null;
    
    // Use the first (most confident) pose
    final landmarks = _extractLandmarks(poses.first);
    
    // Verify we have the essential landmarks for biomechanics
    final required = ['leftelbow', 'rightelbow', 'leftshoulder', 'rightshoulder'];
    final hasRequired = required.any((key) => landmarks.containsKey(key));
    
    if (!hasRequired && kDebugMode) {
      debugPrint('Warning: Missing essential landmarks (elbow/shoulder)');
    }
    
    return landmarks;
  } catch (e) {
    if (kDebugMode) debugPrint('Error in processFrame: $e');
    return null;
  }
}

InputImage? _convertToInputImage(CameraImage image, CameraController controller) {
  try {
    final camera = controller.description;
    final sensorOrientation = camera.sensorOrientation;

    InputImageRotation? rotation;
    if (io.Platform.isIOS) {
      rotation = InputImageRotationValue.fromRawValue(sensorOrientation);
    } else if (io.Platform.isAndroid) {
      final rotationCompensation = _orientations[controller.value.deviceOrientation];
      if (rotationCompensation == null) return null;
      int comp = rotationCompensation;
      if (camera.lensDirection == CameraLensDirection.front) {
        comp = (sensorOrientation + comp) % 360;
      } else {
        comp = (sensorOrientation - comp + 360) % 360;
      }
      rotation = InputImageRotationValue.fromRawValue(comp);
    } else {
      return null;
    }

    if (rotation == null) return null;

    final width = image.width;
    final height = image.height;

    Uint8List bytes;
    if (io.Platform.isAndroid) {
      if (image.planes.length == 1) {
        final plane = image.planes[0];
        final expectedLen = width * height * 3 ~/ 2;
        if (plane.bytes.length >= expectedLen) {
          bytes = Uint8List.fromList(plane.bytes.sublist(0, expectedLen));
        } else {
          return null;
        }
      } else if (image.planes.length == 3) {
        bytes = _yuv420ToNv21(image);
        if (bytes.isEmpty) return null;
      } else {
        return null;
      }
    } else {
      final WriteBuffer wb = WriteBuffer();
      for (final Plane plane in image.planes) {
        wb.putUint8List(plane.bytes);
      }
      bytes = wb.done().buffer.asUint8List();
    }

    final format = io.Platform.isAndroid
        ? InputImageFormat.nv21
        : (InputImageFormatValue.fromRawValue(image.format.raw) ?? InputImageFormat.nv21);
    final bytesPerRow = io.Platform.isAndroid
        ? width
        : (image.planes.isNotEmpty ? image.planes.first.bytesPerRow : width);

    final metadata = InputImageMetadata(
      size: Size(width.toDouble(), height.toDouble()),
      rotation: rotation,
      format: format,
      bytesPerRow: bytesPerRow,
    );

    return InputImage.fromBytes(bytes: bytes, metadata: metadata);
  } catch (_) {
    return null;
  }
}

Uint8List _yuv420ToNv21(CameraImage image) {
  final int width = image.width;
  final int height = image.height;
  final out = Uint8List(width * height * 3 ~/ 2);
  final yPlane = image.planes[0];
  final uPlane = image.planes[1];
  final vPlane = image.planes[2];
  final yRowStride = yPlane.bytesPerRow;
  final uRowStride = uPlane.bytesPerRow;
  final vRowStride = vPlane.bytesPerRow;

  int outIdx = 0;
  for (int y = 0; y < height; y++) {
    for (int x = 0; x < width; x++) {
      out[outIdx++] = yPlane.bytes[y * yRowStride + x];
    }
  }
  for (int y = 0; y < height ~/ 2; y++) {
    for (int x = 0; x < width ~/ 2; x++) {
      out[outIdx++] = vPlane.bytes[y * vRowStride + x];
      out[outIdx++] = uPlane.bytes[y * uRowStride + x];
    }
  }
  return out;
}

/// Extract landmarks from Google ML Kit Pose to BiomechanicsCoach format.
/// Maps PoseLandmarkType enum names (camelCase) to lowercase keys expected by BiomechanicsCoach.
Map<String, Map<String, double>> _extractLandmarks(Pose pose) {
  final lm = <String, Map<String, double>>{};
  
  pose.landmarks.forEach((type, landmark) {
    // Convert enum name (e.g., "leftElbow") to lowercase key (e.g., "leftelbow")
    // This matches what BiomechanicsCoach expects
    final key = type.name.toLowerCase();
    
    lm[key] = {
      'x': landmark.x,
      'y': landmark.y,
      'vis': landmark.likelihood,
    };
  });
  
  // Debug: log available landmarks (only in debug mode)
  if (kDebugMode && lm.isNotEmpty) {
    final keys = lm.keys.toList()..sort();
    debugPrint('ML Kit detected ${lm.length} landmarks: ${keys.join(", ")}');
  }
  
  return lm;
}
