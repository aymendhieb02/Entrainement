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
  String feedback = "READY";
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
    
    if (db['exercises'][exerciseKey] == null) {
      print("Exercise $exerciseKey not found!");
      return;
    }

    exInfo = db['exercises'][exerciseKey];
    template = db['base_templates'][exInfo['uses_template']];
    // Default to 'side' view, or first available
    String viewName = template['primary_view'] ?? 'side';
    if (!template['views'].containsKey(viewName)) {
        viewName = template['views'].keys.first;
    }
    viewCfg = template['views'][viewName];
    
    print("Initialized $exerciseKey with view $viewName");
  }

  double calculateAngle(Map<String, double> a, Map<String, double> b, Map<String, double> c) {
    double baX = a['x']! - b['x']!;
    double baY = a['y']! - b['y']!;
    double bcX = c['x']! - b['x']!;
    double bcY = c['y']! - b['y']!;
    
    double dotProduct = baX * bcX + baY * bcY;
    double magnitudeBA = sqrt(baX * baX + baY * baY);
    double magnitudeBC = sqrt(bcX * bcX + bcY * bcY);
    
    if (magnitudeBA == 0 || magnitudeBC == 0) return 180.0;

    double cosineAngle = dotProduct / (magnitudeBA * magnitudeBC);
    cosineAngle = cosineAngle.clamp(-1.0, 1.0);
    
    return acos(cosineAngle) * 180 / pi;
  }

  int processForm(Map<String, Map<String, double>> landmarks, double currentTimestamp) {
    try {
        // Determine which side is visible
        // Default to left if landmarks missing
        double leftVis = landmarks['leftelbow']?['vis'] ?? 0;
        double rightVis = landmarks['rightelbow']?['vis'] ?? 0;
        
        String side = leftVis > rightVis ? "left" : "right";
        
        bool frameIsExcellent = true;
        List<String> currentIssues = [];

        // Process each joint in the view config
        viewCfg.forEach((jointName, cfg) {
        Map<String, List<String>> ptsMap = {
            'elbow': ['${side}shoulder', '${side}elbow', '${side}wrist'],
            'shoulder': ['${side}hip', '${side}shoulder', '${side}elbow'],
            // 'hip': ['${side}shoulder', '${side}hip', '${side}knee'], // naming might vary in your JSON
             'knee': ['${side}hip', '${side}knee', '${side}ankle'],
        };

        if (!ptsMap.containsKey(jointName)) return;
        
        List<String> jointKeys = ptsMap[jointName]!;
        // check if all keys exist
        if (!jointKeys.every((k) => landmarks.containsKey(k))) return;

        List<Map<String, double>> pts = jointKeys
            .map((p) => landmarks[p]!)
            .toList();

        double angle = calculateAngle(pts[0], pts[1], pts[2]);

        if (cfg['type'] == 'primary') {
            currentAngle = angle;
        } else if (cfg['type'] == 'stability') {
            double target = (cfg['target'] ?? 180).toDouble();
            double maxDev = (cfg['max_deviation'] ?? 15).toDouble();
            
            if ((angle - target).abs() > maxDev) {
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

        // Rep counter logic (simplified for primary joint)
        // Find primary joint config
        var primaryJoint = template['primary_joint'];
        if (viewCfg.containsKey(primaryJoint)) {
            var pCfg = viewCfg[primaryJoint];
            double flexedTarget = (pCfg['flexed'] ?? pCfg['bent'] ?? 90).toDouble();
            double extendedTarget = (pCfg['extended'] ?? pCfg['standing'] ?? 170).toDouble();
            
            // Basic Hysteresis
            if (currentAngle <= (flexedTarget + 20)) {
                if (stage == "extended") stage = "flexed";
            }
            if (currentAngle >= (extendedTarget - 20)) {
                if (stage == "flexed") {
                    reps++;
                    stage = "extended";
                }
            }
        }
    } catch (e) {
        print("Error processing form: $e");
    }

    return reps;
  }
}
