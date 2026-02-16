"""
Transformini Coach - Streamlit app with LIVE camera (same UX as main.py).
Run: streamlit run streamlit_app.py
Uses streamlit-webrtc for real-time webcam; pose via MediaPipe solutions API only (mediapipe==0.10.30).
"""
import time
import streamlit as st
from biomechanics import (
    load_db, BiomechanicsCoach, prettify_exercise_name,
    get_categories_list, get_exercises_list, get_first_valid_exercise_key,
)
st.sidebar.header("Debug")
try:
    import mediapipe as mp, cv2, numpy as np
    st.sidebar.text(f"mediapipe: {mp.__version__}")
    st.sidebar.text(f"cv2: {cv2.__version__}")
    st.sidebar.text(f"numpy: {np.__version__}")
except Exception as e:
    st.sidebar.text(f"debug import error: {e}")
# Shared state for the video frame callback (runs in another thread)
LIVE_STATE = {"coach": None, "analysis_active": False}

# Initialize pose using only mp.solutions.pose (same as main.py); requires mediapipe==0.10.30
POSE_AVAILABLE = False
pose = None
mp_pose = None
cv2 = np = None
_pose_import_traceback = None

import traceback
try:
    import cv2
    import numpy as np
    import mediapipe as mp
    mp_pose = mp.solutions.pose
    try:
        pose = mp_pose.Pose(
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
            model_complexity=0,
        )
        POSE_AVAILABLE = True
    except Exception:
        _pose_import_traceback = traceback.format_exc()
except Exception:
    _pose_import_traceback = traceback.format_exc()
    try:
        import cv2
        import numpy as np
    except Exception:
        cv2 = np = None


def process_frame_and_draw(img_bgr, coach, current_time):
    """Run pose, update coach, draw overlay on img_bgr. Returns same or annotated frame."""
    if not POSE_AVAILABLE or cv2 is None or pose is None or mp_pose is None:
        return img_bgr
    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    h, w = img_bgr.shape[:2]
    try:
        results = pose.process(rgb)
    except Exception:
        return img_bgr
    if not results or not results.pose_landmarks or not coach:
        return img_bgr
    # Build lm dict like main.py: mp_pose.PoseLandmark(i).name.replace("_", "").lower()
    landmarks = results.pose_landmarks.landmark
    lm = {
        mp_pose.PoseLandmark(i).name.replace("_", "").lower(): {"x": l.x, "y": l.y, "vis": l.visibility}
        for i, l in enumerate(landmarks)
    }
    coach.process_form(lm, current_time)
    # Draw joint circles (same as main.py)
    joint_colors = getattr(coach, "joint_colors", {})
    for name, color in joint_colors.items():
        if hasattr(mp_pose.PoseLandmark, name):
            idx = getattr(mp_pose.PoseLandmark, name)
            pt = results.pose_landmarks.landmark[idx]
            x, y = int(pt.x * w), int(pt.y * h)
            col = (0, 255, 136) if color == (0, 255, 0) else (255, 68, 68)
            cv2.circle(img_bgr, (x, y), 15, col, -1)
            cv2.circle(img_bgr, (x, y), 15, (255, 255, 255), 2)
    # Overlay text (like main.py)
    cv2.rectangle(img_bgr, (0, 0), (w, 100), (20, 20, 20), -1)
    cv2.putText(img_bgr, f"REPS: {coach.reps}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 245, 255), 2)
    cv2.putText(img_bgr, coach.feedback, (20, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 136), 2)
    if coach.form_issue:
        cv2.putText(img_bgr, coach.form_issue[:50], (20, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 100, 100), 1)
    return img_bgr


# ---- Page config and CSS (match index.html) ----
st.set_page_config(page_title="Transformini Coach", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    .stApp { background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%); min-height: 100vh; }
    .stApp header { background: transparent !important; }
    .block-container { max-width: 1200px; padding: 2rem; background: rgba(255,255,255,0.05); border-radius: 20px; 
        backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.18); box-shadow: 0 8px 32px rgba(31,38,135,0.37); margin-top: 1rem; }
    h1 { font-family: 'Inter', sans-serif !important; background: linear-gradient(45deg, #00f5ff, #00ff88) !important; 
        -webkit-background-clip: text !important; -webkit-text-fill-color: transparent !important; font-weight: 800 !important; text-align: center !important; }
    .stCaption { color: rgba(255,255,255,0.7) !important; }
    [data-testid="stSidebar"] { background: rgba(255,255,255,0.05) !important; border: 1px solid rgba(255,255,255,0.18) !important; }
    [data-testid="stSidebar"] .stSelectbox label, [data-testid="stSidebar"] p { color: rgba(255,255,255,0.9) !important; }
    [data-testid="stSidebar"] [data-baseweb="select"] { background: rgba(255,255,255,0.1) !important; color: white !important; border-color: rgba(255,255,255,0.2) !important; }
    .stButton > button { background: linear-gradient(45deg, #00f5ff, #00ff88) !important; color: #0f0c29 !important; font-weight: 700 !important; border: none !important; border-radius: 10px !important; text-transform: uppercase !important; letter-spacing: 1px !important; box-shadow: 0 4px 15px rgba(0,245,255,0.3) !important; }
    .stButton > button:hover { box-shadow: 0 6px 20px rgba(0,245,255,0.5) !important; transform: translateY(-2px) !important; }
    [data-testid="stMetricValue"] { color: #00f5ff !important; font-weight: 600 !important; }
    [data-testid="stMetricLabel"] { color: rgba(255,255,255,0.6) !important; }
    p, span, label { color: rgba(255,255,255,0.9) !important; }
</style>
""", unsafe_allow_html=True)

st.title("Transformini Coach")
st.caption("Live camera — your device feed is analyzed in real time. Allow camera when prompted; click Start below to begin the stream.")

# Debug sidebar showing installed versions / import errors when deploying
with st.sidebar:
    st.header("Debug")
    try:
        import importlib
        # show versions when available
        try:
            import mediapipe as _mp
            st.text(f"mediapipe: {_mp.__version__}")
        except Exception:
            st.text("mediapipe: not available")
        try:
            import cv2 as _cv2
            st.text(f"cv2: {_cv2.__version__}")
        except Exception:
            st.text("cv2: not available")
        try:
            import numpy as _np
            st.text(f"numpy: {_np.__version__}")
        except Exception:
            st.text("numpy: not available")
    except Exception:
        st.text("debug: import check failed")
    # show full traceback if pose initialization failed
    try:
        if _pose_import_traceback:
            st.text("pose init traceback:")
            st.code(_pose_import_traceback)
    except Exception:
        pass

@st.cache_data
def get_db():
    return load_db()

db = get_db()
categories = get_categories_list(db)

if "coach" not in st.session_state:
    first_key = get_first_valid_exercise_key(db)
    st.session_state.current_exercise_key = first_key
    st.session_state.coach = BiomechanicsCoach(first_key, db)
if "analysis_started" not in st.session_state:
    st.session_state.analysis_started = True

# Sidebar: exercise selection and Start/Stop
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

    start_clicked = st.button("Start analysis", type="primary")
    stop_clicked = st.button("Stop analysis")
    if start_clicked and not st.session_state.analysis_started:
        st.session_state.analysis_started = True
        st.session_state.coach.reps = 0
        st.session_state.coach.stage = "extended"
        st.session_state.coach.feedback = "READY"
        st.session_state.coach.form_issue = ""
        st.rerun()
    if stop_clicked and st.session_state.analysis_started:
        st.session_state.analysis_started = False
        st.rerun()

    st.metric("Current exercise", prettify_exercise_name(db["exercises"][st.session_state.current_exercise_key]["full_name"]))

coach = st.session_state.coach
LIVE_STATE["coach"] = coach
LIVE_STATE["analysis_active"] = st.session_state.analysis_started

if not POSE_AVAILABLE:
    st.warning("Pose analysis unavailable (install mediapipe==0.10.30 and opencv-python-headless). You still get live camera.")

# Live camera via WebRTC
def video_frame_callback(frame):
    import av
    img = frame.to_ndarray(format="bgr24")
    active = LIVE_STATE.get("analysis_active", False)
    c = LIVE_STATE.get("coach")
    try:
        if active and c and POSE_AVAILABLE and cv2 is not None:
            img = process_frame_and_draw(img, c, time.time())
        elif not active and cv2 is not None:
            h, w = img.shape[:2]
            cv2.rectangle(img, (0, 0), (w, 50), (30, 30, 40), -1)
            cv2.putText(img, "Click 'Start analysis' in the sidebar", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
    except Exception:
        pass
    return av.VideoFrame.from_ndarray(img, format="bgr24")

try:
    from streamlit_webrtc import webrtc_streamer
    webrtc_streamer(
        key="live_camera",
        video_frame_callback=video_frame_callback,
        media_stream_constraints={"video": True, "audio": False},
        async_processing=True,
    )
except Exception as e:
    st.error(f"Live camera failed: {e}. Install streamlit-webrtc and allow camera access.")
    st.code("pip install streamlit-webrtc")

# Metrics (update when you rerun; live values are on the video overlay)
st.markdown("---")
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("REPS", coach.reps)
with col2:
    st.metric("Feedback", coach.feedback)
with col3:
    st.metric("Form", coach.form_issue or "OK")
try:
    span = coach.extended_target - coach.flexed_target
    if span and span > 0:
        progress = 1.0 - (max(coach.flexed_target, min(coach.extended_target, coach.current_angle)) - coach.flexed_target) / span
        progress = max(0.0, min(1.0, progress))
        st.progress(progress, text="Range of motion")
except Exception:
    pass

if not st.session_state.analysis_started:
    st.info("Click **Start analysis** in the sidebar to see reps and form feedback on the video.")
