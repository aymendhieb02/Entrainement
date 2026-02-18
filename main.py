"""
Transformini Coach - Flask backend (ngrok-compatible, client-side camera)
"""
import sys, os, time, threading, base64

if "streamlit" in sys.modules:
    import runpy
    _dir = os.path.dirname(os.path.abspath(__file__))
    runpy.run_path(os.path.join(_dir, "streamlit_app.py"), run_name="__main__")
    sys.exit(0)

import cv2
import numpy as np
import mediapipe as mp
from flask import Flask, render_template, jsonify, request

from biomechanics import (
    load_db, BiomechanicsCoach, prettify_exercise_name,
    is_exercise_valid_for_ui, get_first_valid_exercise_key,
    get_categories_list, get_exercises_list,
)

basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__, template_folder=os.path.join(basedir, "templates"))

# ── Database & coach init ──────────────────────────────────────────────
db = load_db()
current_exercise_key = get_first_valid_exercise_key(db) or "BBCurl"
if not is_exercise_valid_for_ui(current_exercise_key, db):
    current_exercise_key = get_first_valid_exercise_key(db)

exercise_lock = threading.Lock()
coach         = BiomechanicsCoach(current_exercise_key, db)
analysis_active = False

# ── MediaPipe (server-side, for landmark extraction) ───────────────────
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
    model_complexity=0          # lite model – faster on server
)

# ── Helpers ────────────────────────────────────────────────────────────
def _safe_joint_colors(coach_obj):
    """Return joint_colors as a JSON-serializable dict.
    Backend stores tuples like (0, 255, 0); convert to lists for JSON.
    """
    out = {}
    for k, v in getattr(coach_obj, 'joint_colors', {}).items():
        out[k] = list(v) if isinstance(v, (tuple, list)) else v
    return out

def _progress(coach_obj):
    """Return range-of-motion progress 0.0-1.0 (1.0 = fully flexed)."""
    try:
        span = coach_obj.extended_target - coach_obj.flexed_target
        if not span or span <= 0:
            return 0.0
        norm = np.clip(coach_obj.current_angle,
                       coach_obj.flexed_target, coach_obj.extended_target)
        return float(1.0 - (norm - coach_obj.flexed_target) / span)
    except Exception:
        return 0.0

# ── Routes ─────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/analyze/frame", methods=["POST"])
def analyze_frame():
    global coach, analysis_active

    if not analysis_active:
        return jsonify({
            "status":       "paused",
            "reps":         0,
            "feedback":     "PAUSED",
            "form_issue":   "",
            "pose_detected":False,
            "joint_colors": {},
            "progress":     0.0
        })

    # ── Parse body ──
    data = request.get_json(silent=True)
    if not data or "image" not in data:
        return jsonify({"error": "No image provided"}), 400

    try:
        # Decode JPEG
        img_bytes = base64.b64decode(data["image"])
        np_arr    = np.frombuffer(img_bytes, np.uint8)
        frame     = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if frame is None:
            return jsonify({"error": "Invalid image data"}), 400

        # MediaPipe inference
        rgb     = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = pose.process(rgb)

        pose_detected = False
        if results.pose_landmarks:
            pose_detected = True
            lm = {
                mp_pose.PoseLandmark(i).name.replace("_", "").lower(): {
                    "x": l.x, "y": l.y, "vis": l.visibility
                }
                for i, l in enumerate(results.pose_landmarks.landmark)
            }
            with exercise_lock:
                coach.process_form(lm, time.time())

        # Build response AFTER processing
        with exercise_lock:
            resp = {
                "status":       "active",
                "reps":         coach.reps,
                "feedback":     coach.feedback,
                "form_issue":   getattr(coach, 'form_issue', ''),
                "pose_detected":pose_detected,
                "joint_colors": _safe_joint_colors(coach),
                "progress":     _progress(coach),
            }
        return jsonify(resp)

    except Exception as exc:
        import traceback; traceback.print_exc()
        return jsonify({
            "error":        str(exc),
            "status":       "error",
            "reps":         0,
            "feedback":     "ERROR",
            "form_issue":   "",
            "pose_detected":False,
            "joint_colors": {},
            "progress":     0.0
        }), 500


@app.route("/api/categories")
def get_categories():
    return jsonify(get_categories_list(db))


@app.route("/api/exercises/<category>")
def get_exercises_by_category(category):
    return jsonify(get_exercises_list(db, category))


@app.route("/api/select_exercise", methods=["POST"])
def select_exercise():
    global coach, current_exercise_key
    data         = request.get_json(silent=True) or {}
    exercise_key = data.get("exercise_key")
    if not exercise_key:
        return jsonify({"error": "No exercise_key provided"}), 400
    if exercise_key not in db["exercises"]:
        return jsonify({"error": "Exercise not found"}), 404
    if not is_exercise_valid_for_ui(exercise_key, db):
        return jsonify({"error": "Exercise has no metrics"}), 400
    with exercise_lock:
        current_exercise_key = exercise_key
        coach = BiomechanicsCoach(exercise_key, db)
    return jsonify({
        "success":       True,
        "exercise_key":  exercise_key,
        "exercise_name": prettify_exercise_name(db["exercises"][exercise_key]["full_name"])
    })


@app.route("/api/current_exercise")
def get_current_exercise():
    with exercise_lock:
        return jsonify({
            "exercise_key":  current_exercise_key,
            "exercise_name": prettify_exercise_name(db["exercises"][current_exercise_key]["full_name"]),
            "category":      db["exercises"][current_exercise_key]["category"],
        })


@app.route("/api/analysis/start", methods=["POST"])
def start_analysis():
    global analysis_active, coach
    with exercise_lock:
        coach.reps      = 0
        coach.stage     = "extended"
        coach.feedback  = "READY"
        coach.form_issue = ""
    analysis_active = True
    return jsonify({"success": True, "analysis_active": True})


@app.route("/api/analysis/stop", methods=["POST"])
def stop_analysis():
    global analysis_active
    analysis_active = False
    return jsonify({"success": True, "analysis_active": False})


if __name__ == "__main__":
    print("Transformini Coach (Flask)")
    print("Default exercise:", current_exercise_key)
    print("http://127.0.0.1:5000")
    try:
        app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
    finally:
        pose.close()
