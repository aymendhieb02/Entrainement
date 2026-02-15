import cv2
import json
import numpy as np
import mediapipe as mp
from collections import deque
import time
import os
import threading
import re
from flask import Flask, Response, render_template, jsonify, request

# --- CONFIGURATION ---
PATH_JSON = 'complete_exercise_biomechanics_database.json'
CAMERA_INDEX = 0  # 0 for default webcam

# --- ANALYSIS STATE ---
# Camera should open immediately, but analysis should only run
# after the user explicitly clicks "Start Analysis" in the UI.
analysis_active = False

# --- UI HELPERS ---
# Human‑friendly exercise names + validity filtering
NAME_PREFIX_MAP = {
    "BB": "Barbell ",
    "DB": "Dumbbell ",
    "CB": "Cable ",
    "BW": "Bodyweight ",
    "LV": "Machine ",
    "ST": "Strength Training ",
    "AS": "Assisted " ,
    "Wt": "Weight ",
    "SM": "Smith Machine",
    "SI": "Stability Index ",
    "TB": "Trap Bar"
}

def prettify_exercise_name(raw_name: str) -> str:
    """Turn dataset exercise codes into readable names.
    Tries all prefix lengths (longest first) so SI, Wt, AS, SM, etc. are expanded.
    Example: WtTricepsDip -> 'Weight Triceps dip', ASTricepsDip -> 'Assisted Triceps dip'
    """
    if not raw_name:
        return ""

    prefix = ""
    core = raw_name

    # Try matching prefixes from longest to shortest (e.g. 2 chars: SM, SI, Wt, AS, BB, ...)
    for length in sorted([len(k) for k in NAME_PREFIX_MAP], reverse=True):
        if len(raw_name) >= length and raw_name[:length] in NAME_PREFIX_MAP:
            prefix = NAME_PREFIX_MAP[raw_name[:length]]
            core = raw_name[length:]
            break

    # Split CamelCase into words
    words = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])", core)
    name = " ".join(w.lower() for w in words).strip()
    if name:
        name = name[0].upper() + name[1:]

    return (prefix + name).strip()

# Global variables for dynamic exercise selection (set to first valid after db load)
current_exercise_key = "BBCurl"
exercise_lock = threading.Lock()  # Thread-safe exercise switching

class BiomechanicsCoach:
    def __init__(self, exercise_key, database):
        self.db = database
        self.ex_info = self.db['exercises'].get(exercise_key)
        self.template = self.db['base_templates'][self.ex_info['uses_template']]
        
        # dynamic view selection
        self.primary_view_name = self.template.get('primary_view', 'side')
        if self.primary_view_name not in self.template['views']:
             # Fallback to first available view if primary isn't found
             self.primary_view_name = next(iter(self.template['views']))
        
        self.view_cfg = self.template['views'][self.primary_view_name]
        
        # --- DYNAMIC PRIMARY JOINT SELECTION ---
        # Instead of hardcoding 'elbow', we look at the template's 'primary_joint' field
        self.primary_joint_name = self.template['primary_joint']
        
        # Standards from JSON for the specific primary joint
        # Safety check: if primary joint not in view config, use the first available joint
        if self.primary_joint_name not in self.view_cfg:
            # Try to find a joint that is marked as 'primary' in the view config
            for joint, cfg in self.view_cfg.items():
                if cfg.get('type') == 'primary':
                    self.primary_joint_name = joint
                    break
            else:
                 # Fallback to first key
                 self.primary_joint_name = next(iter(self.view_cfg))

        primary_cfg = self.view_cfg[self.primary_joint_name]
        
        # Handle exercises with different naming for standing/parallel vs flexed/extended
        self.flexed_target = primary_cfg.get('flexed') or primary_cfg.get('parallel') or primary_cfg.get('bent')
        self.extended_target = primary_cfg.get('extended') or primary_cfg.get('standing') or primary_cfg.get('lockout')

        # Tolerance from template (used to tighten rep logic)
        self.primary_tolerance = primary_cfg.get('tolerance', 15)
        # Stricter thresholds so random movements are less likely to count as reps
        self.rep_flex_threshold = self.flexed_target + self.primary_tolerance * 0.5
        self.rep_ext_threshold = self.extended_target - self.primary_tolerance * 0.5

        # Minimum visibility required for landmarks to be considered reliable
        self.min_visibility = 0.6
        
        # --- REP COUNTER ---
        self.reps = 0
        self.stage = "extended" 
        self.current_angle = 180
        
        # --- STABILITY & SMOOTHING ---
        # --- STABILITY & SMOOTHING ---
        self.feedback = "READY"
        self.form_issue = ""
        self.joint_colors = {}
        self.smoothing_buffer = deque(maxlen=20) 
        self.last_bad_form_time = 0
        self.warning_duration = 2.0
        
        # --- DETAILED METRICS FOR UI ---
        self.target_feedback = ""     # e.g. "Target: < 90"
        self.current_feedback = ""    # e.g. "Current: 110"
        self.stability_feedback = ""  # e.g. "Torso: Unstable"
        self.last_valid_results = None
        self.last_valid_time = 0.0

    def _calculate_angle(self, a, b, c):
        ba = np.array([a['x'] - b['x'], a['y'] - b['y']])
        bc = np.array([c['x'] - b['x'], c['y'] - b['y']])
        cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc))
        return np.degrees(np.arccos(np.clip(cosine_angle, -1.0, 1.0)))

    def process_form(self, lm, current_timestamp):
        # Which side drives rep counter (better visibility)
        primary_left_key = f"left{self.primary_joint_name}"
        primary_right_key = f"right{self.primary_joint_name}"
        if primary_left_key in lm and primary_right_key in lm:
            primary_side = "left" if lm[primary_left_key]['vis'] >= lm[primary_right_key]['vis'] else "right"
        else:
            primary_side = "left" if lm.get('leftelbow', {'vis': 0})['vis'] > lm.get('rightelbow', {'vis': 0})['vis'] else "right"

        frame_is_excellent = True
        self.joint_colors = {}
        current_issues = []
        self.stability_feedback = "Stability: OK"
        primary_grace = 15  # Green when at full extension OR good depth (so it stays green through the rep)

        pts_map_template = {
            'elbow': ['shoulder', 'elbow', 'wrist'],
            'shoulder': ['hip', 'shoulder', 'elbow'],
            'hip': ['shoulder', 'hip', 'knee'],
            'knee': ['hip', 'knee', 'ankle'],
            'ankle': ['knee', 'ankle', 'footindex']
        }

        # --- BOTH SIDES: compute angles and colors for left and right ---
        primary_angles = {"left": 180, "right": 180}
        for side in ("left", "right"):
            for joint_name, cfg in self.view_cfg.items():
                if joint_name not in pts_map_template:
                    continue
                keys = [f"{side}{p}" for p in pts_map_template[joint_name]]
                pts = [lm.get(k, {'x': 0, 'y': 0, 'vis': 0}) for k in keys]
                if any(p['vis'] < self.min_visibility for p in pts):
                    continue
                angle = self._calculate_angle(*pts)
                status = "green"

                if joint_name == self.primary_joint_name:
                    primary_angles[side] = angle

                if cfg.get('type') == "stability":
                    target = cfg.get('target') or cfg.get('upright') or 180
                    max_dev = cfg.get('max_deviation') or 15
                    if abs(angle - target) > max_dev:
                        status = "red"
                        frame_is_excellent = False
                        current_issues.append(f"STABILIZE {joint_name.upper()}")
                        self.stability_feedback = f"{joint_name.title()}: {int(angle)}\u00b0 (Target ~{target}\u00b0)"

                self.joint_colors[f"{side.upper()}_{joint_name.upper()}"] = (0, 255, 0) if status == "green" else (0, 0, 255)

        # Rep counter uses primary side only
        self.current_angle = primary_angles[primary_side]

        # --- FEEDBACK text (one side drives the message) ---
        if self.stage == "extended":
            if self.current_angle > self.rep_flex_threshold:
                self.feedback = "GO FURTHER"
            else:
                self.feedback = "GOOD DEPTH"
        elif self.stage == "flexed":
            if self.current_angle < self.rep_ext_threshold:
                self.feedback = "FULL EXTENSION"
            else:
                self.feedback = "GOOD EXTENSION"
        else:
            pass

        form_ok = (current_timestamp - self.last_bad_form_time) >= self.warning_duration
        if not form_ok:
            self.feedback = "FIX FORM"
            self.form_issue = current_issues[0] if current_issues else ""
        else:
            self.form_issue = current_issues[0] if current_issues else ""

        # --- PRIMARY JOINT COLOR (both sides): green when form OK and (at full extension OR at good depth)
        # So when you fully extend or fully flex, dot stays green; red only in the "in-between" wrong zone
        for side in ("left", "right"):
            angle = primary_angles[side]
            pk = f"{side.upper()}_{self.primary_joint_name.upper()}"
            if pk not in self.joint_colors:
                continue
            if not form_ok:
                primary_status = "red"
            else:
                # Green if at full extension (high angle) OR at good depth (low angle)
                at_full_extension = angle >= (self.rep_ext_threshold - primary_grace)
                at_good_depth = angle <= (self.rep_flex_threshold + primary_grace)
                primary_status = "green" if (at_full_extension or at_good_depth) else "red"
            self.joint_colors[pk] = (0, 255, 0) if primary_status == "green" else (0, 0, 255)

        # Update smoothing
        self.smoothing_buffer.append(frame_is_excellent)
        bad_frame_count = self.smoothing_buffer.count(False)
        if bad_frame_count > (self.smoothing_buffer.maxlen * 0.3):
            self.last_bad_form_time = current_timestamp
            if current_issues:
                self.form_issue = current_issues[0]

        # --- REP COUNTER: only when form is good ---
        if not form_ok:
            return self.reps
        if self.current_angle <= self.rep_flex_threshold:
            if self.stage == "extended":
                self.stage = "flexed"
        if self.current_angle >= self.rep_ext_threshold:
            if self.stage == "flexed":
                self.reps += 1
                self.stage = "extended"

        return self.reps

# --- FLASK APP ---
# Get the directory where this script is located
basedir = os.path.abspath(os.path.dirname(__file__))
template_dir = os.path.join(basedir, 'templates')

app = Flask(__name__, template_folder=template_dir)

# Load database
with open(PATH_JSON, 'r') as f:
    db = json.load(f)

def is_exercise_valid_for_ui(exercise_key: str) -> bool:
    """Return True only if the exercise has a valid primary joint with
    usable flexed/extended (or equivalent) angles for rep counting.
    This hides entries that have no real biomechanics rules defined.
    """
    try:
        ex_info = db['exercises'].get(exercise_key)
        if not ex_info:
            return False

        template_name = ex_info.get('uses_template')
        if not template_name:
            return False

        template = db['base_templates'].get(template_name)
        if not template:
            return False

        views = template.get('views') or {}
        if not views:
            return False

        # Primary view selection (mirror of BiomechanicsCoach logic)
        primary_view_name = template.get('primary_view', 'side')
        if primary_view_name not in views:
            primary_view_name = next(iter(views))

        view_cfg = views.get(primary_view_name, {})
        if not view_cfg:
            return False

        # Primary joint selection
        primary_joint_name = template.get('primary_joint')
        if not primary_joint_name:
            return False

        if primary_joint_name not in view_cfg:
            for joint, cfg in view_cfg.items():
                if cfg.get('type') == 'primary':
                    primary_joint_name = joint
                    break
            else:
                primary_joint_name = next(iter(view_cfg))

        primary_cfg = view_cfg.get(primary_joint_name, {})
        if not primary_cfg:
            return False

        flexed = primary_cfg.get('flexed') or primary_cfg.get('parallel') or primary_cfg.get('bent')
        extended = primary_cfg.get('extended') or primary_cfg.get('standing') or primary_cfg.get('lockout')

        return flexed is not None and extended is not None
    except Exception:
        # If anything about the template is broken, treat it as invalid for UI
        return False

def get_first_valid_exercise_key():
    """Return the first exercise key that is valid for UI (has metrics/template)."""
    for key, exercise_data in db['exercises'].items():
        if exercise_data.get('uses_template') and is_exercise_valid_for_ui(key):
            return key
    return "BBCurl"  # fallback if none valid

# Ensure default exercise has metrics so UI never starts on invalid exercise
if not is_exercise_valid_for_ui(current_exercise_key):
    current_exercise_key = get_first_valid_exercise_key()

# Initialize coach with default exercise
coach = BiomechanicsCoach(current_exercise_key, db)
mp_pose = mp.solutions.pose
# 0.5 confidence + lite model for easier full-body detection without stepping far back
pose = mp_pose.Pose(
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
    model_complexity=0  # 0=lite (better for full body in frame)
)
mp_drawing = mp.solutions.drawing_utils

# Global camera object (request 1280x720 so more of the scene is captured if supported)
# On Railway/cloud there is no webcam; app still runs and shows a placeholder feed.
camera = cv2.VideoCapture(CAMERA_INDEX)
CAMERA_AVAILABLE = camera.isOpened()
if CAMERA_AVAILABLE:
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    try:
        camera.set(27, 0.5)  # CAP_PROP_ZOOM on some drivers
    except Exception:
        pass

def _placeholder_frame_bytes():
    """Single JPEG frame for when camera is not available (e.g. Railway deploy)."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[:] = (30, 30, 40)
    cv2.putText(frame, "Camera not available", (80, 220), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2)
    cv2.putText(frame, "Run locally for live analysis", (60, 270), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (180, 180, 180), 1)
    ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return buffer.tobytes()

def generate_frames():
    """Generator function that yields video frames with biomechanics overlay"""
    global coach, current_exercise_key, analysis_active
    if not CAMERA_AVAILABLE:
        # No webcam (e.g. Railway): stream a static placeholder
        while True:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + _placeholder_frame_bytes() + b'\r\n')
            time.sleep(0.5)
        return
    frame_count = 0
    start_time = time.time()
    process_every_n_frames = 2  # Process pose every 2 frames for performance
    
    while True:
        success, frame = camera.read()
        if not success:
            break
        
        # Calculate timestamp
        current_time = time.time() - start_time
        frame_count += 1
        
        # Get frame dimensions
        h, w = frame.shape[:2]

        # --- CONDITIONAL ANALYSIS ---
        # Camera is always on, but pose/rep analysis only runs
        # when analysis_active is True (toggled from the UI).
        if analysis_active:
            # Only process pose detection every N frames to reduce lag
            # But allow using cached results for smooth UI
            if frame_count % process_every_n_frames == 0:
                try:
                    # Force synchronous processing for better stability
                    new_results = pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                    
                    if new_results.pose_landmarks:
                        results = new_results
                        # Update cache with timestamp
                        coach.last_valid_results = results
                        coach.last_valid_time = time.time()
                    else:
                        # Detection failed, fallback to cache if recent (<0.5s)
                        if hasattr(coach, 'last_valid_results') and \
                           (time.time() - getattr(coach, 'last_valid_time', 0) < 0.5):
                            results = coach.last_valid_results
                        else:
                            results = None
                except Exception as e:
                    print(f"Pose processing error: {e}")
                    # Fallback on error
                    if hasattr(coach, 'last_valid_results') and \
                       (time.time() - getattr(coach, 'last_valid_time', 0) < 0.5):
                        results = coach.last_valid_results
                    else:
                        results = None
            else:
                # Use cached results on skipped frames if recent
                if hasattr(coach, 'last_valid_results') and \
                   (time.time() - getattr(coach, 'last_valid_time', 0) < 0.5):
                    results = coach.last_valid_results
                else:
                    results = None
            
            if results and results.pose_landmarks:
                lm = {mp_pose.PoseLandmark(i).name.replace('_','').lower(): 
                      {'x': l.x, 'y': l.y, 'vis': l.visibility} 
                      for i, l in enumerate(results.pose_landmarks.landmark)}
                
                # Thread-safe access to coach
                try:
                    with exercise_lock:
                        reps = coach.process_form(lm, current_time)
                except Exception as e:
                    print(f"Biomechanics processing error: {e}")
                    reps = "ERR"
                    # Don't crash, just show error on screen
                    cv2.putText(frame, "PROCESSING ERROR", (50, 200), 1, 2, (0, 0, 255), 2)

                # UI: Skeleton
                try:
                    mp_drawing.draw_landmarks(frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)
                    with exercise_lock:
                         # Only draw dots if we have valid coach state
                         if hasattr(coach, 'joint_colors'):
                            for mp_name, color in coach.joint_colors.items():
                                if hasattr(mp_pose.PoseLandmark, mp_name):
                                    idx = getattr(mp_pose.PoseLandmark, mp_name)
                                    pt = results.pose_landmarks.landmark[idx]
                                    cv2.circle(frame, (int(pt.x*w), int(pt.y*h)), 15, color, -1)
                except Exception as e:
                    print(f"Drawing error: {e}")

                # UI: Dashboard
                cv2.rectangle(frame, (0, 0), (w, 100), (20, 20, 20), -1)
                cv2.putText(frame, f"REPS: {reps}", (40, 70), 1, 3, (255, 255, 255), 4)
                
                try:
                    with exercise_lock:
                        # --- ENHANCED UI: TARGETS & FEEDBACK ---
                        status_color = (0, 255, 0) if "GOOD" in coach.feedback else (0, 255, 255)
                        if coach.feedback == "FIX FORM": status_color = (0, 0, 255)
                        
                        # 1. Main Feedback
                        cv2.putText(frame, coach.feedback, (200, 45), 1, 2, status_color, 3)
                        
                        # 2. Issue/Stability Alert
                        if coach.form_issue:
                            cv2.putText(frame, coach.form_issue, (200, 85), 1, 1.5, (0, 0, 255), 2)

                        # 3. Green progress bar (range of motion) at bottom
                        try:
                            span = coach.extended_target - coach.flexed_target
                            if span and span > 0:
                                norm_angle = np.clip(coach.current_angle, coach.flexed_target, coach.extended_target)
                                progress = 1.0 - (norm_angle - coach.flexed_target) / span
                                progress = np.clip(progress, 0.0, 1.0)
                                bar_w = int(w * progress)
                                cv2.rectangle(frame, (0, h - 12), (w, h), (40, 40, 40), -1)
                                cv2.rectangle(frame, (0, h - 12), (bar_w, h), (0, 255, 0), -1)
                        except Exception:
                            pass
                except Exception as e:
                    print(f"Dashboard error: {e}")
        else:
            # When analysis is not active, show a simple banner so user
            # knows the camera is on but movement is not being tracked.
            cv2.rectangle(frame, (0, 0), (w, 60), (20, 20, 20), -1)
            cv2.putText(frame, "Analysis paused - click 'Start Analysis' to begin",
                        (40, 40), 1, 1.2, (255, 255, 255), 2)

        # Encode frame as JPEG with compression for better performance
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        frame = buffer.tobytes()
        
        # Yield frame in byte format
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/test')
def test():
    """Simple test route"""
    return "Flask is working! If you see this, the server is running correctly."

@app.route('/')
def index():
    """Render the main page"""
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    """Video streaming route"""
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/categories')
def get_categories():
    """Get list of unique exercise categories for valid exercises only.
    Thighs and Calves are grouped under a single 'Legs' category.
    """
    categories = set()
    for key, exercise_data in db['exercises'].items():
        if exercise_data.get('uses_template') and is_exercise_valid_for_ui(key):
            cat = exercise_data['category']
            if cat in ('Thighs', 'Calves'):
                categories.add('Legs')
            else:
                categories.add(cat)
    return jsonify(sorted(list(categories)))

@app.route('/api/exercises/<category>')
def get_exercises_by_category(category):
    """Get exercises for a specific category, filtering invalid ones.
    When category is 'Legs', returns exercises from Thighs and Calves.
    """
    exercises = []
    if category == 'Legs':
        allowed_cats = ('Thighs', 'Calves')
    else:
        allowed_cats = (category,)
    for key, exercise_data in db['exercises'].items():
        if exercise_data['category'] in allowed_cats and exercise_data.get('uses_template') and is_exercise_valid_for_ui(key):
            exercises.append({
                'key': key,
                'name': prettify_exercise_name(exercise_data['full_name']),
                'category': exercise_data['category']
            })
    return jsonify(sorted(exercises, key=lambda x: x['name']))

@app.route('/api/select_exercise', methods=['POST'])
def select_exercise():
    """Change the current exercise"""
    global coach, current_exercise_key
    
    data = request.get_json()
    exercise_key = data.get('exercise_key')
    
    if not exercise_key:
        return jsonify({'error': 'No exercise_key provided'}), 400
    
    if exercise_key not in db['exercises']:
        return jsonify({'error': f'Exercise {exercise_key} not found'}), 404
    if not is_exercise_valid_for_ui(exercise_key):
        return jsonify({'error': 'Exercise has no metrics; cannot use for analysis'}), 400

    # Thread-safe exercise switching
    with exercise_lock:
        current_exercise_key = exercise_key
        coach = BiomechanicsCoach(exercise_key, db)
    
    return jsonify({
        'success': True,
        'exercise_key': exercise_key,
        'exercise_name': prettify_exercise_name(db['exercises'][exercise_key]['full_name'])
    })

@app.route('/api/current_exercise')
def get_current_exercise():
    """Get current exercise information"""
    with exercise_lock:
        return jsonify({
            'exercise_key': current_exercise_key,
            'exercise_name': prettify_exercise_name(db['exercises'][current_exercise_key]['full_name']),
            'category': db['exercises'][current_exercise_key]['category']
        })

@app.route('/api/analysis/start', methods=['POST'])
def start_analysis():
    """Start pose/rep analysis while keeping the camera feed running."""
    global analysis_active, coach
    with exercise_lock:
        # Reset counters/feedback at the beginning of a new analysis session
        coach.reps = 0
        coach.stage = "extended"
        coach.feedback = "READY"
        coach.form_issue = ""
        coach.target_feedback = ""
        coach.current_feedback = ""
        coach.stability_feedback = "Stability: OK"
    analysis_active = True
    return jsonify({'success': True, 'analysis_active': True})

@app.route('/api/analysis/stop', methods=['POST'])
def stop_analysis():
    """Stop pose/rep analysis but keep the camera feed alive."""
    global analysis_active
    analysis_active = False
    return jsonify({'success': True, 'analysis_active': False})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("🚀 Starting Biomechanics Coach Web App...")
    print("📹 Camera:", "OK" if CAMERA_AVAILABLE else "Not available (e.g. cloud)")
    print("🏋️  Default Exercise:", current_exercise_key)
    print("📁 Template folder:", template_dir)
    print("🌐 Open your browser at: http://127.0.0.1:{}".format(port))
    print("\nPress CTRL+C to stop the server")
    try:
        app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
    finally:
        if CAMERA_AVAILABLE:
            camera.release()
        pose.close()