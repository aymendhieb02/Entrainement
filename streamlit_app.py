"""
Transformini Coach - Streamlit app.
Run: streamlit run streamlit_app.py
Deploy on share.streamlit.io (transformini-training-feedback).
"""
import time
import streamlit as st
from biomechanics import (
    load_db, BiomechanicsCoach, prettify_exercise_name,
    get_categories_list, get_exercises_list, get_first_valid_exercise_key,
    is_exercise_valid_for_ui
)

# Try to load cv2 and mediapipe (use opencv-python-headless on Streamlit Cloud)
try:
    import cv2
    import numpy as np
    import mediapipe as mp
    POSE_AVAILABLE = True
    mp_pose = mp.solutions.pose
    pose = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5, model_complexity=0)
except (ImportError, OSError) as e:
    POSE_AVAILABLE = False
    cv2 = np = mp = mp_pose = pose = None
    st.warning(f"Pose analysis unavailable: {e}. Install opencv-python-headless and mediapipe.")

st.set_page_config(page_title="Transformini Coach", layout="wide")
st.title("Transformini Coach")
st.caption("Real-time form feedback — capture a frame to analyze.")

@st.cache_data
def get_db():
    return load_db()

db = get_db()
categories = get_categories_list(db)

# Session state
if "coach" not in st.session_state:
    first_key = get_first_valid_exercise_key(db)
    st.session_state.current_exercise_key = first_key
    st.session_state.coach = BiomechanicsCoach(first_key, db)
if "analysis_started" not in st.session_state:
    st.session_state.analysis_started = False

# Sidebar
with st.sidebar:
    st.header("Exercise")
    cat = st.selectbox("Category", categories, key="cat")
    exercises = get_exercises_list(db, cat)
    ex_options = {x["name"]: x["key"] for x in exercises}
    ex_name = st.selectbox("Exercise", list(ex_options.keys()) if ex_options else ["No exercises"], key="ex_name")
    if ex_options and ex_name:
        new_key = ex_options[ex_name]
        if new_key != st.session_state.current_exercise_key:
            st.session_state.current_exercise_key = new_key
            st.session_state.coach = BiomechanicsCoach(new_key, db)
    if st.button("Start analysis", type="primary") and not st.session_state.analysis_started:
        st.session_state.analysis_started = True
        st.session_state.coach.reps = 0
        st.session_state.coach.stage = "extended"
        st.session_state.coach.feedback = "READY"
        st.session_state.coach.form_issue = ""
        st.rerun()
    if st.button("Stop analysis") and st.session_state.analysis_started:
        st.session_state.analysis_started = False
        st.rerun()
    st.metric("Current exercise", prettify_exercise_name(db["exercises"][st.session_state.current_exercise_key]["full_name"]))

# Main: camera input and analysis
if not POSE_AVAILABLE:
    st.info("Install opencv-python-headless and mediapipe in requirements to enable pose analysis.")
    st.stop()

coach = st.session_state.coach
img_bytes = st.camera_input("Capture a frame to analyze form")

if img_bytes and st.session_state.analysis_started:
    buf = img_bytes.getvalue()
    nparr = __import__("numpy").frombuffer(buf, dtype=np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is not None:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = pose.process(rgb)
        if results.pose_landmarks:
            lm = {}
            for i, l in enumerate(results.pose_landmarks.landmark):
                name = mp_pose.PoseLandmark(i).name.replace("_", "").lower()
                lm[name] = {"x": l.x, "y": l.y, "vis": l.visibility}
            coach.process_form(lm, time.time())
        # Draw joints on image with PIL
        from PIL import Image, ImageDraw
        h, w = frame.shape[:2]
        img_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img_pil)
        if results.pose_landmarks:
            for name, color in getattr(coach, "joint_colors", {}).items():
                if hasattr(mp_pose.PoseLandmark, name):
                    idx = getattr(mp_pose.PoseLandmark, name)
                    pt = results.pose_landmarks.landmark[idx]
                    x, y = int(pt.x * w), int(pt.y * h)
                    fill = (0, 255, 136) if color == (0, 255, 0) else (255, 68, 68)
                    draw.ellipse([x - 12, y - 12, x + 12, y + 12], fill=fill, outline=(255, 255, 255))
        st.image(img_pil, use_container_width=True)

# Metrics
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("REPS", coach.reps)
with col2:
    st.metric("Feedback", coach.feedback)
with col3:
    st.metric("Form", coach.form_issue or "OK")

# Progress bar (range of motion)
try:
    span = coach.extended_target - coach.flexed_target
    if span and span > 0:
        progress = 1.0 - (max(coach.flexed_target, min(coach.extended_target, coach.current_angle)) - coach.flexed_target) / span
        progress = max(0.0, min(1.0, progress))
        st.progress(progress, text="Range of motion")
except Exception:
    pass

if not st.session_state.analysis_started:
    st.info("Select an exercise and click **Start analysis** in the sidebar, then capture a frame.")
