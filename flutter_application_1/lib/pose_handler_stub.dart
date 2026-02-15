// Stub for web: Google ML Kit is not supported on web.
import 'package:camera/camera.dart';

Object? createPoseDetector() => null;

Future<Map<String, Map<String, double>>?> processFrame(
  CameraImage image,
  Object? detector,
  CameraController controller,
) async =>
    null;

void closePoseDetector(Object? detector) {}
