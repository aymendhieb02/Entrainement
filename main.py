"""
Transformini Coach - Local Flask app (optional).
For deployment use Streamlit: streamlit run streamlit_app.py
"""
import time
import threading
import cv2
import numpy as np
import mediapipe as mp
from flask import Flask, Response, render_template, jsonify, request

from biomechanics import (
    load_db, BiomechanicsCoach, prettify_exercise_name,
    is_exercise_valid_for_ui, get_first_valid_exercise_key,
    get_categories_list, get_exercises_list,
)

basedir = __import__("os").path.abspath(__import__("os").path.dirname(__file__))
app = Flask(__name__, template_folder=__import__("os").path.join(basedir, "templates"))

db = load_db()
current_exercise_key = get_first_valid_exercise_key(db) if get_first_valid_exercise_key(db) else "BBCurl"
if not is_exercise_valid_for_ui(current_exercise_key, db):
    current_exercise_key = get_first_valid_exercise_key(db)
exercise_lock = threading.Lock()
coach = BiomechanicsCoach(current_exercise_key, db)
analysis_active = False

mp_pose = mp.solutions.pose
pose = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5, model_complexity=0)
mp_drawing = mp.solutions.drawing_utils
CAMERA_INDEX = 0
camera = cv2.VideoCapture(CAMERA_INDEX)
CAMERA_AVAILABLE = camera.isOpened()
if CAMERA_AVAILABLE:
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)


def generate_frames():
    global coach, current_exercise_key, analysis_active
    if not CAMERA_AVAILABLE:
        from PIL import Image, ImageDraw
        import io
        while True:
            img = Image.new("RGB", (640, 480), (30, 30, 40))
            draw = ImageDraw.Draw(img)
            draw.text((80, 220), "Camera not available", fill=(255, 255, 255))
            draw.text((60, 270), "Use Streamlit app or run with a camera", fill=(180, 180, 180))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buf.getvalue() + b'\r\n')
            time.sleep(0.5)
        return
    frame_count = 0
    start_time = time.time()
    while True:
        success, frame = camera.read()
        if not success:
            break
        current_time = time.time() - start_time
        frame_count += 1
        h, w = frame.shape[:2]
        if analysis_active and frame_count % 2 == 0:
            try:
                new_results = pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                if new_results.pose_landmarks:
                    results = new_results
                    coach.last_valid_results = results
                    coach.last_valid_time = time.time()
                else:
                    results = coach.last_valid_results if (getattr(coach, 'last_valid_time', 0) and time.time() - coach.last_valid_time < 0.5) else None
            except Exception:
                results = coach.last_valid_results if (getattr(coach, 'last_valid_time', 0) and time.time() - coach.last_valid_time < 0.5) else None
        else:
            results = coach.last_valid_results if (getattr(coach, 'last_valid_time', 0) and time.time() - coach.last_valid_time < 0.5) else None
        if analysis_active and results and results.pose_landmarks:
            lm = {mp_pose.PoseLandmark(i).name.replace("_", "").lower(): {"x": l.x, "y": l.y, "vis": l.visibility} for i, l in enumerate(results.pose_landmarks.landmark)}
            with exercise_lock:
                reps = coach.process_form(lm, current_time)
            try:
                mp_drawing.draw_landmarks(frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)
                for mp_name, color in getattr(coach, "joint_colors", {}).items():
                    if hasattr(mp_pose.PoseLandmark, mp_name):
                        idx = getattr(mp_pose.PoseLandmark, mp_name)
                        pt = results.pose_landmarks.landmark[idx]
                        cv2.circle(frame, (int(pt.x * w), int(pt.y * h)), 15, color, -1)
            except Exception:
                pass
            cv2.rectangle(frame, (0, 0), (w, 100), (20, 20, 20), -1)
            cv2.putText(frame, f"REPS: {reps}", (40, 70), 1, 3, (255, 255, 255), 4)
            status_color = (0, 255, 0) if "GOOD" in coach.feedback else (0, 255, 255)
            if coach.feedback == "FIX FORM":
                status_color = (0, 0, 255)
            cv2.putText(frame, coach.feedback, (200, 45), 1, 2, status_color, 3)
            if coach.form_issue:
                cv2.putText(frame, coach.form_issue, (200, 85), 1, 1.5, (0, 0, 255), 2)
        else:
            cv2.rectangle(frame, (0, 0), (w, 60), (20, 20, 20), -1)
            cv2.putText(frame, "Analysis paused - click Start in the UI", (40, 40), 1, 1.2, (255, 255, 255), 2)
        ret, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/video_feed")
def video_feed():
    return Response(generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/api/categories")
def get_categories():
    return jsonify(get_categories_list(db))


@app.route("/api/exercises/<category>")
def get_exercises_by_category(category):
    return jsonify(get_exercises_list(db, category))


@app.route("/api/select_exercise", methods=["POST"])
def select_exercise():
    global coach, current_exercise_key
    data = request.get_json()
    exercise_key = (data or {}).get("exercise_key")
    if not exercise_key:
        return jsonify({"error": "No exercise_key provided"}), 400
    if exercise_key not in db["exercises"]:
        return jsonify({"error": "Exercise not found"}), 404
    if not is_exercise_valid_for_ui(exercise_key, db):
        return jsonify({"error": "Exercise has no metrics"}), 400
    with exercise_lock:
        current_exercise_key = exercise_key
        coach = BiomechanicsCoach(exercise_key, db)
    return jsonify({"success": True, "exercise_key": exercise_key, "exercise_name": prettify_exercise_name(db["exercises"][exercise_key]["full_name"])})


@app.route("/api/current_exercise")
def get_current_exercise():
    with exercise_lock:
        return jsonify({
            "exercise_key": current_exercise_key,
            "exercise_name": prettify_exercise_name(db["exercises"][current_exercise_key]["full_name"]),
            "category": db["exercises"][current_exercise_key]["category"],
        })


@app.route("/api/analysis/start", methods=["POST"])
def start_analysis():
    global analysis_active, coach
    with exercise_lock:
        coach.reps = 0
        coach.stage = "extended"
        coach.feedback = "READY"
        coach.form_issue = ""
    analysis_active = True
    return jsonify({"success": True, "analysis_active": True})


@app.route("/api/analysis/stop", methods=["POST"])
def stop_analysis():
    global analysis_active
    analysis_active = False
    return jsonify({"success": True, "analysis_active": False})


if __name__ == "__main__":
    print("Transformini Coach (Flask - local)")
    print("Default exercise:", current_exercise_key)
    print("http://127.0.0.1:5000")
    try:
        app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
    finally:
        if CAMERA_AVAILABLE and camera:
            camera.release()
        pose.close()
