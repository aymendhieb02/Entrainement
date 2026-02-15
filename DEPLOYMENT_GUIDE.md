# 🚀 Exercise Form Analyzer - Deployment Guide

## Project Structure
```
exercise-analyzer/
├── api_server.py          # Flask API server
├── test_client.html       # Browser test client
├── requirements.txt       # Python dependencies
├── README.md             # This file
└── flutter_integration/  # Flutter code examples
```

---

## 📋 Prerequisites

### For Local Testing:
- Python 3.8+
- Webcam
- Modern browser (Chrome/Firefox)

### For Production:
- Linux server (Ubuntu 20.04+ recommended)
- 2GB+ RAM
- GPU optional (runs fine on CPU)

---

## 🔧 Installation

### 1. Install Python Dependencies

```bash
# Create virtual environment (recommended)
python -m venv venv

# Activate it
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Start the API Server

```bash
python api_server.py
```

You should see:
```
🚀 Exercise Analyzer API Server
==================================================
Available endpoints:
  GET  /api/health - Health check
  GET  /api/exercises - List exercises
  POST /api/analyze/image - Analyze frame
  POST /api/analyze/reset - Reset session
  POST /api/load-calibration - Load calibration
==================================================
Starting server on http://localhost:5000
```

### 3. Test with Browser Client

Open `test_client.html` in your browser (you may need to serve it via HTTP):

```bash
# Simple Python HTTP server
python -m http.server 8000
```

Then navigate to: `http://localhost:8000/test_client.html`

---

## 🔌 API Documentation

### GET /api/health
Check if server is running

**Response:**
```json
{
  "status": "healthy",
  "version": "2.0",
  "available_exercises": ["squat", "bicep_curl", "push_up"]
}
```

### GET /api/exercises
Get list of available exercises

**Response:**
```json
{
  "exercises": [
    {
      "name": "squat",
      "display_name": "Squat",
      "primary_joint": "knee"
    }
  ]
}
```

### POST /api/analyze/image
Analyze a single frame

**Request:**
```json
{
  "exercise": "squat",
  "image": "data:image/jpeg;base64,/9j/4AAQSkZJRg..."
}
```

**Response:**
```json
{
  "success": true,
  "image": "data:image/jpeg;base64,...",
  "feedback": {
    "reps": 5,
    "phase": "down",
    "angle": 95.3,
    "status": "EXCELLENT!",
    "color": [0, 255, 0],
    "quality": 87.5
  }
}
```

### POST /api/analyze/reset
Reset rep counter and session state

**Request:**
```json
{
  "exercise": "squat"
}
```

### POST /api/load-calibration
Load custom calibration thresholds

**Request:**
```json
{
  "exercise": "squat",
  "thresholds": {
    "down": 110,
    "up": 160,
    "excellent_min": 90,
    "excellent_max": 105,
    "too_deep": 80
  }
}
```

---

## 📱 Flutter Integration

### 1. Add Dependencies

In your `pubspec.yaml`:
```yaml
dependencies:
  flutter:
    sdk: flutter
  http: ^1.1.0
  camera: ^0.10.5
  image: ^4.1.3
```

### 2. Flutter Service Class

```dart
import 'dart:convert';
import 'dart:typed_data';
import 'package:http/http.dart' as http;

class ExerciseAnalyzerService {
  final String baseUrl;
  
  ExerciseAnalyzerService({this.baseUrl = 'http://localhost:5000'});
  
  // Check if API is available
  Future<bool> checkHealth() async {
    try {
      final response = await http.get(Uri.parse('$baseUrl/api/health'));
      return response.statusCode == 200;
    } catch (e) {
      return false;
    }
  }
  
  // Get available exercises
  Future<List<Exercise>> getExercises() async {
    final response = await http.get(Uri.parse('$baseUrl/api/exercises'));
    
    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return (data['exercises'] as List)
          .map((e) => Exercise.fromJson(e))
          .toList();
    }
    throw Exception('Failed to load exercises');
  }
  
  // Analyze a frame
  Future<AnalysisResult> analyzeFrame({
    required String exercise,
    required Uint8List imageBytes,
  }) async {
    // Convert image to base64
    final base64Image = base64Encode(imageBytes);
    final imageData = 'data:image/jpeg;base64,$base64Image';
    
    final response = await http.post(
      Uri.parse('$baseUrl/api/analyze/image'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'exercise': exercise,
        'image': imageData,
      }),
    );
    
    if (response.statusCode == 200) {
      return AnalysisResult.fromJson(jsonDecode(response.body));
    }
    throw Exception('Analysis failed: ${response.body}');
  }
  
  // Reset session
  Future<void> resetSession(String exercise) async {
    await http.post(
      Uri.parse('$baseUrl/api/analyze/reset'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'exercise': exercise}),
    );
  }
}

// Data models
class Exercise {
  final String name;
  final String displayName;
  final String primaryJoint;
  
  Exercise({
    required this.name,
    required this.displayName,
    required this.primaryJoint,
  });
  
  factory Exercise.fromJson(Map<String, dynamic> json) => Exercise(
    name: json['name'],
    displayName: json['display_name'],
    primaryJoint: json['primary_joint'],
  );
}

class AnalysisResult {
  final bool success;
  final String? imageBase64;
  final Feedback? feedback;
  
  AnalysisResult({
    required this.success,
    this.imageBase64,
    this.feedback,
  });
  
  factory AnalysisResult.fromJson(Map<String, dynamic> json) => AnalysisResult(
    success: json['success'],
    imageBase64: json['image'],
    feedback: json['feedback'] != null 
        ? Feedback.fromJson(json['feedback'])
        : null,
  );
}

class Feedback {
  final int reps;
  final String phase;
  final double angle;
  final String status;
  final List<int> color;
  final double? quality;
  
  Feedback({
    required this.reps,
    required this.phase,
    required this.angle,
    required this.status,
    required this.color,
    this.quality,
  });
  
  factory Feedback.fromJson(Map<String, dynamic> json) => Feedback(
    reps: json['reps'],
    phase: json['phase'],
    angle: json['angle'].toDouble(),
    status: json['status'],
    color: List<int>.from(json['color']),
    quality: json['quality']?.toDouble(),
  );
}
```

### 3. Flutter UI Example

```dart
import 'package:flutter/material.dart';
import 'package:camera/camera.dart';
import 'dart:typed_data';

class ExerciseAnalyzerScreen extends StatefulWidget {
  @override
  _ExerciseAnalyzerScreenState createState() => _ExerciseAnalyzerScreenState();
}

class _ExerciseAnalyzerScreenState extends State<ExerciseAnalyzerScreen> {
  final service = ExerciseAnalyzerService(baseUrl: 'http://YOUR_SERVER_IP:5000');
  
  CameraController? _cameraController;
  bool _isAnalyzing = false;
  Feedback? _currentFeedback;
  String _selectedExercise = 'squat';
  
  @override
  void initState() {
    super.initState();
    _initializeCamera();
  }
  
  Future<void> _initializeCamera() async {
    final cameras = await availableCameras();
    _cameraController = CameraController(
      cameras.first,
      ResolutionPreset.medium,
      enableAudio: false,
    );
    await _cameraController!.initialize();
    setState(() {});
  }
  
  void _startAnalysis() {
    setState(() => _isAnalyzing = true);
    _analyzeFrames();
  }
  
  void _analyzeFrames() async {
    while (_isAnalyzing) {
      if (_cameraController == null || !_cameraController!.value.isInitialized) {
        await Future.delayed(Duration(milliseconds: 100));
        continue;
      }
      
      try {
        // Capture frame
        final image = await _cameraController!.takePicture();
        final bytes = await image.readAsBytes();
        
        // Send to API
        final result = await service.analyzeFrame(
          exercise: _selectedExercise,
          imageBytes: bytes,
        );
        
        if (result.success && result.feedback != null) {
          setState(() => _currentFeedback = result.feedback);
        }
      } catch (e) {
        print('Analysis error: $e');
      }
      
      // ~10 FPS
      await Future.delayed(Duration(milliseconds: 100));
    }
  }
  
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('Exercise Analyzer'),
        backgroundColor: Colors.deepPurple,
      ),
      body: Column(
        children: [
          // Camera preview
          Expanded(
            child: _cameraController?.value.isInitialized ?? false
                ? CameraPreview(_cameraController!)
                : Center(child: CircularProgressIndicator()),
          ),
          
          // Stats overlay
          Container(
            padding: EdgeInsets.all(20),
            color: Colors.black87,
            child: Column(
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceAround,
                  children: [
                    _buildStatCard('Reps', '${_currentFeedback?.reps ?? 0}'),
                    _buildStatCard('Quality', 
                      _currentFeedback?.quality != null 
                        ? '${_currentFeedback!.quality!.toStringAsFixed(1)}%'
                        : '-'
                    ),
                  ],
                ),
                SizedBox(height: 10),
                Text(
                  _currentFeedback?.status ?? 'READY',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 24,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
          ),
          
          // Controls
          Padding(
            padding: EdgeInsets.all(20),
            child: Row(
              children: [
                Expanded(
                  child: ElevatedButton(
                    onPressed: _isAnalyzing ? null : _startAnalysis,
                    child: Text('Start'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.green,
                      padding: EdgeInsets.symmetric(vertical: 15),
                    ),
                  ),
                ),
                SizedBox(width: 10),
                Expanded(
                  child: ElevatedButton(
                    onPressed: !_isAnalyzing ? null : () {
                      setState(() => _isAnalyzing = false);
                    },
                    child: Text('Stop'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.red,
                      padding: EdgeInsets.symmetric(vertical: 15),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
  
  Widget _buildStatCard(String label, String value) {
    return Column(
      children: [
        Text(label, style: TextStyle(color: Colors.white70, fontSize: 14)),
        SizedBox(height: 5),
        Text(value, style: TextStyle(color: Colors.white, fontSize: 28, fontWeight: FontWeight.bold)),
      ],
    );
  }
  
  @override
  void dispose() {
    _cameraController?.dispose();
    super.dispose();
  }
}
```

---

## 🌐 Production Deployment

### Option 1: Docker (Recommended)

Create `Dockerfile`:
```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY api_server.py .

EXPOSE 5000

CMD ["python", "api_server.py"]
```

Build and run:
```bash
docker build -t exercise-analyzer .
docker run -p 5000:5000 exercise-analyzer
```

### Option 2: Traditional Server

```bash
# Install dependencies
sudo apt update
sudo apt install python3-pip python3-venv

# Create app directory
cd /opt
sudo mkdir exercise-analyzer
cd exercise-analyzer

# Setup virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create systemd service
sudo nano /etc/systemd/system/exercise-analyzer.service
```

Service file:
```ini
[Unit]
Description=Exercise Analyzer API
After=network.target

[Service]
User=www-data
WorkingDirectory=/opt/exercise-analyzer
Environment="PATH=/opt/exercise-analyzer/venv/bin"
ExecStart=/opt/exercise-analyzer/venv/bin/python api_server.py

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable exercise-analyzer
sudo systemctl start exercise-analyzer
```

### Option 3: Cloud Platforms

#### AWS EC2
1. Launch t2.medium instance (Ubuntu)
2. Install Python and dependencies
3. Configure security group (port 5000)
4. Use Nginx as reverse proxy

#### Google Cloud Run
1. Build Docker image
2. Push to Container Registry
3. Deploy to Cloud Run
4. Auto-scales based on traffic

#### Heroku
```bash
# Create Procfile
echo "web: python api_server.py" > Procfile

# Deploy
heroku create exercise-analyzer-api
git push heroku main
```

---

## ⚡ Performance Optimization

### 1. Use GPU Acceleration (if available)
MediaPipe automatically uses GPU when available. No code changes needed!

### 2. Reduce Frame Rate
In Flutter, increase delay between frames:
```dart
await Future.delayed(Duration(milliseconds: 200)); // 5 FPS instead of 10
```

### 3. Image Compression
Reduce image quality before sending:
```dart
final compressed = await FlutterImageCompress.compressWithList(
  bytes,
  quality: 70,
);
```

### 4. Batch Processing (Advanced)
Send multiple frames in one request to reduce network overhead.

---

## 🔒 Security Considerations

### 1. Add API Key Authentication

In `api_server.py`:
```python
from functools import wraps

API_KEY = "your-secret-key"

def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get('X-API-Key')
        if key != API_KEY:
            return jsonify({'error': 'Invalid API key'}), 401
        return f(*args, **kwargs)
    return decorated

@app.route('/api/analyze/image', methods=['POST'])
@require_api_key
def analyze_image():
    # ... existing code
```

### 2. Rate Limiting
```bash
pip install flask-limiter
```

```python
from flask_limiter import Limiter

limiter = Limiter(app, key_func=lambda: request.remote_addr)

@app.route('/api/analyze/image', methods=['POST'])
@limiter.limit("100 per minute")
def analyze_image():
    # ... existing code
```

### 3. HTTPS in Production
Always use HTTPS with Let's Encrypt or cloud provider SSL.

---

## 🐛 Troubleshooting

### Issue: "MediaPipe import error"
**Solution:** Install specific version
```bash
pip install mediapipe==0.10.9
```

### Issue: "CORS errors from Flutter"
**Solution:** Update CORS settings in `api_server.py`:
```python
CORS(app, origins=['http://localhost:*', 'https://yourapp.com'])
```

### Issue: "Camera not working in Flutter"
**Solution:** Add permissions:
- iOS: `Info.plist` camera usage description
- Android: `AndroidManifest.xml` camera permission

### Issue: "Slow processing"
**Solution:**
1. Reduce image resolution
2. Increase frame delay
3. Use GPU if available
4. Consider edge processing

---

## 📊 Monitoring

### Add Logging
```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route('/api/analyze/image', methods=['POST'])
def analyze_image():
    logger.info(f"Analysis request for {exercise}")
    # ... existing code
```

### Metrics to Track
- Requests per minute
- Average processing time
- Error rate
- User session duration

---

## 🎯 Next Steps

1. ✅ Test locally with browser client
2. ✅ Integrate with Flutter app
3. ⬜ Add more exercises
4. ⬜ Implement user authentication
5. ⬜ Add workout history/tracking
6. ⬜ Deploy to production
7. ⬜ Add analytics dashboard

---

## 📞 Support

For issues or questions:
1. Check troubleshooting section
2. Review API logs
3. Test with browser client first
4. Verify network connectivity

---

## 📄 License

This project is provided as-is for educational and commercial use.
