import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:camera/camera.dart';
import 'package:permission_handler/permission_handler.dart';
import 'biomechanics_coach.dart';
import 'platform_io.dart' if (dart.library.html) 'platform_stub.dart' as io;
import 'pose_handler.dart' if (dart.library.html) 'pose_handler_stub.dart' as pose_handler;

/// User-friendly message and tips for camera errors.
String _cameraErrorMessage(Object e) {
  if (e is CameraException) {
    final code = e.code.toLowerCase();
    final desc = e.description ?? e.code;
    if (code.contains('notreadable') || code.contains('hardware')) {
      return 'Camera is in use or not accessible.\n\n'
          '• Close other apps or browser tabs using the camera\n'
          '• If in browser: try Chrome and allow camera for this site\n'
          '• Refresh the page and allow camera when asked\n'
          '• On phone: use the app (APK) for best results';
    }
    if (code.contains('permission') || code.contains('denied')) {
      return 'Camera permission was denied.\n\n'
          'Allow camera access in your browser or device settings, then tap Retry.';
    }
    return desc;
  }
  return e.toString().replaceFirst(RegExp(r'^Exception:?\s*'), '');
}

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Biomechanics Coach',
      theme: ThemeData(
        primarySwatch: Colors.blue,
        useMaterial3: true,
      ),
      home: const BiomechanicsScreen(),
    );
  }
}

class BiomechanicsScreen extends StatefulWidget {
  const BiomechanicsScreen({super.key});

  @override
  State<BiomechanicsScreen> createState() => _BiomechanicsScreenState();
}

class _BiomechanicsScreenState extends State<BiomechanicsScreen> {
  CameraController? _cameraController;
  Object? _poseDetector; // PoseDetector on mobile, null on web

  final BiomechanicsCoach _coach = BiomechanicsCoach();

  bool _isCameraInitialized = false;
  bool _isProcessing = false;
  DateTime? _lastPoseDetectedAt;
  int _framesProcessed = 0;
  int _framesWithPose = 0;
  String? _initError;
  bool _isInitializing = true;

  final String _currentExercise = 'BBCurl';

  @override
  void initState() {
    super.initState();
    _initialize();
  }

  Future<void> _initialize() async {
    if (!mounted) return;
    setState(() {
      _initError = null;
      _isInitializing = true;
    });

    try {
      await _requestPermissions();
      await _coach.initialize(_currentExercise);
      await _initializeCamera();
      if (!kIsWeb) {
        _poseDetector = pose_handler.createPoseDetector();
        if (mounted && _cameraController != null) {
          _cameraController!.startImageStream(_processCameraImage);
        }
      }
    } catch (e, st) {
      if (kDebugMode) debugPrint('Init error: $e\n$st');
      if (mounted) {
        setState(() {
          _initError = _cameraErrorMessage(e);
          _isInitializing = false;
        });
      }
      return;
    }

    if (mounted) {
      setState(() => _isInitializing = false);
    }
  }

  Future<void> _requestPermissions() async {
    try {
      await Permission.camera.request();
      if (!kIsWeb) await Permission.microphone.request();
    } catch (_) {}
  }

  ImageFormatGroup _getImageFormatGroup() {
    if (kIsWeb) return ImageFormatGroup.bgra8888;
    if (io.Platform.isAndroid) return ImageFormatGroup.nv21;
    return ImageFormatGroup.bgra8888;
  }

  Future<void> _initializeCamera() async {
    final cameras = await availableCameras();
    if (cameras.isEmpty) {
      throw Exception('No camera found. Allow camera access and refresh.');
    }
    final camera = cameras.firstWhere(
      (c) => c.lensDirection == CameraLensDirection.front,
      orElse: () => cameras.first,
    );

    _cameraController = CameraController(
      camera,
      ResolutionPreset.medium,
      enableAudio: false,
      imageFormatGroup: _getImageFormatGroup(),
    );

    await _cameraController!.initialize();

    if (mounted) {
      setState(() => _isCameraInitialized = true);
    }
  }

  void _processCameraImage(CameraImage image) async {
    if (_isProcessing || _poseDetector == null || _cameraController == null) return;
    _isProcessing = true;

    try {
      _framesProcessed++;
      final landmarks = await pose_handler.processFrame(
        image,
        _poseDetector,
        _cameraController!,
      );

      if (landmarks != null) {
        _framesWithPose++;
        _lastPoseDetectedAt = DateTime.now();
        final timestamp = DateTime.now().millisecondsSinceEpoch / 1000.0;
        _coach.processForm(landmarks, timestamp);
      }

      if (mounted) setState(() {});
    } catch (e) {
      if (kDebugMode) debugPrint('Pose processing error: $e');
    } finally {
      _isProcessing = false;
    }
  }

  @override
  void dispose() {
    _cameraController?.dispose();
    pose_handler.closePoseDetector(_poseDetector);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_initError != null) {
      return Scaffold(
        body: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const SizedBox(height: 24),
                const Icon(Icons.camera_alt_outlined, size: 64, color: Colors.orange),
                const SizedBox(height: 16),
                const Text(
                  'Camera error',
                  style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 12),
                Text(
                  _initError!,
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: Colors.black87, height: 1.4),
                ),
                const SizedBox(height: 28),
                FilledButton.icon(
                  onPressed: () => _initialize(),
                  icon: const Icon(Icons.refresh),
                  label: const Text('Retry'),
                ),
                const SizedBox(height: 24),
              ],
            ),
          ),
        ),
      );
    }

    if (_isInitializing || !_isCameraInitialized || _cameraController == null) {
      return Scaffold(
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const CircularProgressIndicator(),
              const SizedBox(height: 24),
              Text(
                _isInitializing ? 'Opening camera…' : 'Preparing…',
                style: const TextStyle(color: Colors.grey),
              ),
              if (kIsWeb) ...[
                const SizedBox(height: 8),
                const Text(
                  'Allow camera access when the browser asks.',
                  style: TextStyle(fontSize: 12, color: Colors.grey),
                  textAlign: TextAlign.center,
                ),
              ],
            ],
          ),
        ),
      );
    }

    return Scaffold(
      body: Stack(
        fit: StackFit.expand,
        children: [
          SizedBox.expand(
            child: CameraPreview(_cameraController!),
          ),
          if (kIsWeb)
            Positioned(
              top: 16,
              left: 16,
              right: 16,
              child: Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.black54,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Text(
                  'Camera is on. Pose detection runs on Android/iOS app.',
                  style: TextStyle(color: Colors.white, fontSize: 14),
                ),
              ),
            ),
          if (!kIsWeb) ..._buildOverlay(),
        ],
      ),
    );
  }

  List<Widget> _buildOverlay() {
    return [
      Positioned(
        top: 50,
        left: 20,
        right: 20,
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Colors.black.withOpacity(0.6),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: Colors.cyan.withOpacity(0.5), width: 1),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    _currentExercise,
                    style: const TextStyle(
                        color: Colors.white70, fontSize: 16, fontWeight: FontWeight.bold),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: _coach.feedback == 'EXCELLENT' ? Colors.green : Colors.orange,
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      _coach.feedback,
                      style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('REPS', style: TextStyle(color: Colors.white54, fontSize: 12)),
                      Text(
                        '${_coach.reps}',
                        style: const TextStyle(
                            color: Colors.white, fontSize: 48, fontWeight: FontWeight.bold),
                      ),
                    ],
                  ),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      const Text('ANGLE', style: TextStyle(color: Colors.white54, fontSize: 12)),
                      Text(
                        '${_coach.currentAngle.toInt()}°',
                        style: const TextStyle(
                            color: Colors.white, fontSize: 32, fontWeight: FontWeight.w500),
                      ),
                    ],
                  ),
                ],
              ),
              if (_coach.formIssue.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Text(
                    '⚠️ ${_coach.formIssue}',
                    style: const TextStyle(
                        color: Colors.redAccent, fontSize: 16, fontWeight: FontWeight.bold),
                  ),
                ),
            ],
          ),
        ),
      ),
      Positioned(
        bottom: 20,
        left: 0,
        right: 0,
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                'Phase: ${_coach.stage.toUpperCase()}',
                style: const TextStyle(color: Colors.white54, fontSize: 14),
              ),
              const SizedBox(height: 4),
              Text(
                _lastPoseDetectedAt != null
                    ? 'Pose: OK ($_framesWithPose frames)'
                    : _framesProcessed > 10
                        ? 'Point camera at body'
                        : 'Model: starting…',
                style: TextStyle(
                  color: _lastPoseDetectedAt != null ? Colors.greenAccent : Colors.white54,
                  fontSize: 12,
                ),
              ),
            ],
          ),
        ),
      ),
    ];
  }
}
