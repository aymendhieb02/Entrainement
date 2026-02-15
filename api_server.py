"""
Exercise Form Analyzer - Flask API Server
Provides REST endpoints for real-time exercise analysis
"""

from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import cv2
import mediapipe as mp
import numpy as np
import math
import json
import base64
from collections import deque
import time

app = Flask(__name__)
CORS(app)  # Enable CORS for Flutter/web clients

# ========== CONFIGURATION ==========
SMOOTHING_WINDOW = 7
HYSTERESIS_BUFFER = 5

EXERCISE_CONFIGS = {
    "squat": {
        "primary_joint": "knee",
        "joint_chain": ["Hip", "Knee", "Ankle"],
        "direction": "down",
        "thresholds": {
            "down": 110,
            "up": 160,
            "excellent_min": 90,
            "excellent_max": 105,
            "too_deep": 80
        },
        "feedback_messages": {
            "excellent": "PERFECT DEPTH! 💪",
            "good": "GOOD FORM ✓",
            "deeper": "GO DEEPER ⬇️",
            "too_deep": "TOO LOW! ⚠️"
        }
    },
    "bicep_curl": {
        "primary_joint": "elbow",
        "joint_chain": ["Shoulder", "Elbow", "Wrist"],
        "direction": "down",
        "thresholds": {
            "down": 60,
            "up": 150,
            "excellent_min": 40,
            "excellent_max": 55,
            "too_deep": 30
        },
        "feedback_messages": {
            "excellent": "FULL CONTRACTION! 💪",
            "good": "GOOD CURL ✓",
            "deeper": "CURL HIGHER ⬆️",
            "too_deep": "CONTROLLED! ⚠️"
        }
    },
    "push_up": {
        "primary_joint": "elbow",
        "joint_chain": ["Shoulder", "Elbow", "Wrist"],
        "direction": "down",
        "thresholds": {
            "down": 90,
            "up": 160,
            "excellent_min": 70,
            "excellent_max": 85,
            "too_deep": 60
        },
        "feedback_messages": {
            "excellent": "PERFECT DEPTH! 💪",
            "good": "GOOD PUSH-UP ✓",
            "deeper": "GO LOWER ⬇️",
            "too_deep": "TOO LOW! ⚠️"
        }
    }
}

# ========== UTILITY FUNCTIONS ==========

def get_angle(a, b, c):
    """Calculate angle between three points"""
    try:
        ba = [a['x'] - b['x'], a['y'] - b['y']]
        bc = [c['x'] - b['x'], c['y'] - b['y']]
        dot = ba[0]*bc[0] + ba[1]*bc[1]
        mag_a = math.hypot(*ba)
        mag_c = math.hypot(*bc)
        return math.degrees(math.acos(max(-1, min(1, dot / (mag_a * mag_c)))))
    except:
        return 180.0

class AngleSmoother:
    """Smooth angle values using moving average"""
    def __init__(self, window_size=7):
        self.window = deque(maxlen=window_size)
    
    def smooth(self, angle):
        self.window.append(angle)
        return np.mean(self.window)
    
    def reset(self):
        self.window.clear()

# ========== EXERCISE ANALYZER ==========

class ExerciseAnalyzer:
    def __init__(self, exercise_name):
        self.exercise_name = exercise_name.lower()
        self.config = EXERCISE_CONFIGS.get(self.exercise_name, EXERCISE_CONFIGS["squat"])
        self.thresholds = self.config["thresholds"]
        
        # State
        self.phase = "up"
        self.reps = 0
        self.was_active = False
        self.status = "READY"
        self.color = (255, 255, 255)
        self.feedback_hold_frames = 0
        self.last_feedback = "READY"
        
        # Smoothing
        self.angle_smoother = AngleSmoother(SMOOTHING_WINDOW)
        
        # Quality tracking
        self.rep_quality = []
        self.current_rep_min_angle = 180
        
    def reset(self):
        """Reset analyzer state for new session"""
        self.phase = "up"
        self.reps = 0
        self.was_active = False
        self.rep_quality = []
        self.current_rep_min_angle = 180
        self.angle_smoother.reset()
    
    def analyze(self, lm):
        """Analyze current pose"""
        # Determine which side is more visible
        side = "left" if lm.get('leftKnee', {}).get('vis', 0) > lm.get('rightKnee', {}).get('vis', 0) else "right"
        
        # Get angle from joint chain
        target = [f"{side}{j}" for j in self.config['joint_chain']]
        
        # Check if all joints present
        if not all(t in lm for t in target):
            return {
                'reps': self.reps,
                'phase': self.phase,
                'angle': 180,
                'status': 'POSITION YOURSELF',
                'color': (100, 100, 100),
                'quality': None
            }
        
        raw_angle = get_angle(lm[target[0]], lm[target[1]], lm[target[2]])
        angle = self.angle_smoother.smooth(raw_angle)
        
        # Track minimum angle during down phase
        if self.phase == "down":
            self.current_rep_min_angle = min(self.current_rep_min_angle, angle)
        
        # Phase detection with hysteresis
        if angle < self.thresholds['down'] and self.phase == "up":
            self.phase = "down"
            self.was_active = True
            self.current_rep_min_angle = angle
            
        elif angle > self.thresholds['up'] + HYSTERESIS_BUFFER and self.phase == "down":
            self.phase = "up"
            if self.was_active:
                self.reps += 1
                # Calculate rep quality
                quality = self._calculate_rep_quality(self.current_rep_min_angle)
                self.rep_quality.append(quality)
                self.was_active = False
                self.current_rep_min_angle = 180
                self.last_feedback = self.config['feedback_messages'].get('good', 'GREAT REP!')
                self.feedback_hold_frames = 20  # Hold for ~0.6 seconds at 30fps
        
        # Determine feedback
        if self.feedback_hold_frames > 0:
            self.feedback_hold_frames -= 1
            self.status = self.last_feedback
            self.color = (0, 255, 0)
        elif self.phase == "down":
            if angle <= self.thresholds['too_deep']:
                self.status = self.config['feedback_messages'].get('too_deep', 'TOO LOW!')
                self.color = (0, 165, 255)  # Orange
            elif angle <= self.thresholds['excellent_max']:
                self.status = self.config['feedback_messages'].get('excellent', 'EXCELLENT!')
                self.color = (0, 255, 0)  # Green
            elif angle <= self.thresholds['down']:
                self.status = self.config['feedback_messages'].get('good', 'GOOD!')
                self.color = (0, 255, 255)  # Yellow
            else:
                self.status = self.config['feedback_messages'].get('deeper', 'GO DEEPER!')
                self.color = (0, 0, 255)  # Red
        else:
            self.status = "READY"
            self.color = (255, 255, 255)
        
        return {
            'reps': self.reps,
            'phase': self.phase,
            'angle': round(angle, 1),
            'status': self.status,
            'color': self.color,
            'quality': self._get_average_quality()
        }
    
    def _calculate_rep_quality(self, min_angle):
        """Calculate quality score for a rep (0-100)"""
        excellent_mid = (self.thresholds['excellent_min'] + self.thresholds['excellent_max']) / 2
        distance = abs(min_angle - excellent_mid)
        
        if distance == 0:
            return 100
        elif min_angle <= self.thresholds['excellent_max']:
            return max(80, 100 - distance * 2)
        elif min_angle <= self.thresholds['down']:
            return max(60, 80 - distance)
        else:
            return max(30, 60 - distance)
    
    def _get_average_quality(self):
        """Get average quality of all reps"""
        if not self.rep_quality:
            return None
        return round(sum(self.rep_quality) / len(self.rep_quality), 1)

# ========== MEDIAPIPE SETUP ==========

mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils
pose = mp_pose.Pose(
    static_image_mode=False,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

# Global analyzers for different exercises
analyzers = {}

# ========== UI RENDERING ==========

def draw_enhanced_ui(frame, feedback, exercise_name):
    """Draw enhanced UI with better visuals"""
    h, w = frame.shape[:2]
    
    # Glassmorphic top bar
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 200), (15, 15, 15), -1)
    cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)
    
    # Border gradient effect
    cv2.rectangle(frame, (0, 0), (w, 4), (0, 255, 255), -1)
    cv2.rectangle(frame, (0, 200), (w, 204), (0, 255, 255), -1)
    
    # === LEFT SECTION: REPS ===
    rep_x, rep_y = 25, 45
    cv2.putText(frame, "REPS", (rep_x, rep_y), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (150, 150, 150), 2)
    
    # Large rep counter with glow effect
    rep_size = cv2.getTextSize(str(feedback['reps']), cv2.FONT_HERSHEY_BOLD, 4, 5)[0]
    cv2.putText(frame, str(feedback['reps']), (rep_x, 140), 
                cv2.FONT_HERSHEY_BOLD, 4, (50, 50, 50), 7)  # Shadow
    cv2.putText(frame, str(feedback['reps']), (rep_x, 140), 
                cv2.FONT_HERSHEY_BOLD, 4, (255, 255, 255), 5)
    
    # === CENTER SECTION: STATUS ===
    status_text = feedback['status']
    status_size = cv2.getTextSize(status_text, cv2.FONT_HERSHEY_BOLD, 1.3, 3)[0]
    status_x = (w - status_size[0]) // 2
    
    # Status with shadow
    cv2.putText(frame, status_text, (status_x + 2, 87), 
                cv2.FONT_HERSHEY_BOLD, 1.3, (0, 0, 0), 5)
    cv2.putText(frame, status_text, (status_x, 85), 
                cv2.FONT_HERSHEY_BOLD, 1.3, feedback['color'], 3)
    
    # === RIGHT SECTION: INFO ===
    info_x = w - 200
    
    # Exercise name
    cv2.putText(frame, exercise_name.upper(), (info_x, 45), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (150, 150, 150), 2)
    
    # Phase indicator with colored dot
    phase_color = (0, 255, 0) if feedback['phase'] == 'down' else (100, 100, 100)
    cv2.circle(frame, (info_x, 70), 8, phase_color, -1)
    cv2.putText(frame, f" {feedback['phase'].upper()}", (info_x + 15, 75), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 2)
    
    # Quality score if available
    if feedback.get('quality'):
        quality_color = (0, 255, 0) if feedback['quality'] >= 80 else \
                       (0, 255, 255) if feedback['quality'] >= 60 else (0, 165, 255)
        cv2.putText(frame, f"AVG: {feedback['quality']}%", (info_x, 105), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, quality_color, 2)
    
    # === BOTTOM: DEPTH METER ===
    meter_w = min(500, w - 100)
    meter_x = (w - meter_w) // 2
    meter_y = 145
    meter_h = 35
    
    # Meter background
    cv2.rectangle(frame, (meter_x, meter_y), (meter_x + meter_w, meter_y + meter_h), 
                  (50, 50, 50), -1)
    cv2.rectangle(frame, (meter_x, meter_y), (meter_x + meter_w, meter_y + meter_h), 
                  (100, 100, 100), 2)
    
    # Get thresholds from analyzer
    if exercise_name in analyzers:
        thresh = analyzers[exercise_name].thresholds
        
        # Excellent zone (green)
        exc_start = int((thresh['excellent_min'] / 180) * meter_w)
        exc_end = int((thresh['excellent_max'] / 180) * meter_w)
        cv2.rectangle(frame, (meter_x + exc_start, meter_y + 2), 
                     (meter_x + exc_end, meter_y + meter_h - 2), (0, 200, 0), -1)
        
        # Good zone (yellow)
        good_end = int((thresh['down'] / 180) * meter_w)
        cv2.rectangle(frame, (meter_x + exc_end, meter_y + 2), 
                     (meter_x + good_end, meter_y + meter_h - 2), (0, 200, 200), -1)
        
        # Current angle marker
        current_pos = int((feedback['angle'] / 180) * meter_w)
        current_pos = max(0, min(meter_w, current_pos))
        
        # Marker with glow
        cv2.line(frame, (meter_x + current_pos, meter_y - 8), 
                (meter_x + current_pos, meter_y + meter_h + 8), (255, 255, 255), 5)
        cv2.line(frame, (meter_x + current_pos, meter_y - 8), 
                (meter_x + current_pos, meter_y + meter_h + 8), (0, 255, 255), 2)
        
        # Angle label
        cv2.putText(frame, f"{int(feedback['angle'])}°", 
                   (meter_x + current_pos - 20, meter_y - 15), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    
    return frame

# ========== API ENDPOINTS ==========

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'version': '2.0',
        'available_exercises': list(EXERCISE_CONFIGS.keys())
    })

@app.route('/api/exercises', methods=['GET'])
def get_exercises():
    """Get available exercises"""
    return jsonify({
        'exercises': [
            {
                'name': name,
                'display_name': name.replace('_', ' ').title(),
                'primary_joint': config['primary_joint']
            }
            for name, config in EXERCISE_CONFIGS.items()
        ]
    })

@app.route('/api/analyze/image', methods=['POST'])
def analyze_image():
    """Analyze a single frame"""
    try:
        data = request.json
        exercise = data.get('exercise', 'squat')
        image_b64 = data.get('image')
        
        if not image_b64:
            return jsonify({'error': 'No image provided'}), 400
        
        # Decode image
        img_bytes = base64.b64decode(image_b64.split(',')[1] if ',' in image_b64 else image_b64)
        nparr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # Initialize analyzer if needed
        if exercise not in analyzers:
            analyzers[exercise] = ExerciseAnalyzer(exercise)
        
        analyzer = analyzers[exercise]
        
        # Process frame
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = pose.process(rgb_frame)
        
        if results.pose_landmarks:
            # Extract landmarks
            lm = {}
            for i, landmark in enumerate(results.pose_landmarks.landmark):
                name = mp_pose.PoseLandmark(i).name.replace('_', '').lower()
                side = "left" if "left" in name else "right" if "right" in name else ""
                clean = side + name.replace("left", "").replace("right", "").capitalize()
                lm[clean] = {
                    'x': landmark.x,
                    'y': landmark.y,
                    'vis': landmark.visibility
                }
            
            # Analyze
            feedback = analyzer.analyze(lm)
            
            # Draw UI
            frame = draw_enhanced_ui(frame, feedback, exercise)
            
            # Draw skeleton
            mp_drawing.draw_landmarks(
                frame,
                results.pose_landmarks,
                mp_pose.POSE_CONNECTIONS,
                mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=3),
                mp_drawing.DrawingSpec(color=(0, 255, 255), thickness=2)
            )
            
            # Encode result
            _, buffer = cv2.imencode('.jpg', frame)
            result_b64 = base64.b64encode(buffer).decode('utf-8')
            
            return jsonify({
                'success': True,
                'image': f"data:image/jpeg;base64,{result_b64}",
                'feedback': feedback
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No pose detected'
            }), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analyze/reset', methods=['POST'])
def reset_session():
    """Reset analyzer state"""
    try:
        data = request.json
        exercise = data.get('exercise', 'squat')
        
        if exercise in analyzers:
            analyzers[exercise].reset()
        
        return jsonify({
            'success': True,
            'message': f'{exercise} session reset'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/load-calibration', methods=['POST'])
def load_calibration():
    """Load custom calibration data"""
    try:
        data = request.json
        exercise = data.get('exercise')
        thresholds = data.get('thresholds')
        
        if exercise in EXERCISE_CONFIGS:
            EXERCISE_CONFIGS[exercise]['thresholds'] = thresholds
            
            # Reset analyzer to use new thresholds
            if exercise in analyzers:
                analyzers[exercise] = ExerciseAnalyzer(exercise)
            
            return jsonify({
                'success': True,
                'message': f'Calibration loaded for {exercise}'
            })
        else:
            return jsonify({'error': 'Exercise not found'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("🚀 Exercise Analyzer API Server")
    print("=" * 50)
    print("Available endpoints:")
    print("  GET  /api/health - Health check")
    print("  GET  /api/exercises - List exercises")
    print("  POST /api/analyze/image - Analyze frame")
    print("  POST /api/analyze/reset - Reset session")
    print("  POST /api/load-calibration - Load calibration")
    print("=" * 50)
    print("Starting server on http://localhost:5000")
    print("Press Ctrl+C to stop")
    
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
