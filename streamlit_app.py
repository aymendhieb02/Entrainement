"""
Transformini Coach - Streamlit app with LIVE camera (same UX as main.py).
Run: streamlit run streamlit_app.py
Uses streamlit-webrtc for real-time webcam; pose via MediaPipe Tasks or solutions.
"""
import os
import time
import tempfile
import urllib.request
import streamlit as st
from biomechanics import (
    load_db, BiomechanicsCoach, prettify_exercise_name,
    get_categories_list, get_exercises_list, get_first_valid_exercise_key,
)

# Shared state for the video frame callback (runs in another thread)
LIVE_STATE = {"coach": None, "analysis_active": False}

# 33 pose landmark names in MediaPipe order for coach compatibility
POSE_LANDMARK_NAMES = [
    "nose", "lefteyeinner", "lefteye", "lefteyeouter", "righteyeinner", "righteye", "righteyeouter",
    "leftear", "rightear", "mouthleft", "mouthright",
    "leftshoulder", "rightshoulder", "leftelbow", "rightelbow", "leftwrist", "rightwrist",
    "leftpinky", "rightpinky", "leftindex", "rightindex", "leftthumb", "rightthumb",
    "lefthip", "righthip", "leftknee", "rightknee", "leftankle", "rightankle",
    "leftheel", "rightheel", "leftfootindex", "rightfootindex",
]

def _get_pose_detector_tasks():
    """MediaPipe Tasks API (works with mediapipe 0.10.31+). Use writable path for model."""
    try:
        import cv2
        import numpy as np
        import mediapipe as mp
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision
    except (ImportError, AttributeError):
        return None, None
    # Use /tmp or tempdir so Streamlit Cloud (read-only app dir) can write the model
    model_path = os.path.join(tempfile.gettempdir(), "pose_landmarker.task")
    if not os.path.isfile(model_path):
        try:
            url = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task"
            urllib.request.urlretrieve(url, model_path)
        except Exception:
            return None, None
    try:
        base_options = python.BaseOptions(model_asset_path=model_path)
        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            output_segmentation_masks=False,
        )
        detector = vision.PoseLandmarker.create_from_options(options)
        return detector, mp
    except Exception:
        return None, None

def _get_pose_detector_solutions():
    """Legacy: mp.solutions.pose (mediapipe < 0.10.31)."""
    try:
        import cv2
        import numpy as np
        import mediapipe as mp
        _ = mp.solutions.pose
        pose = mp.solutions.pose.Pose(
            min_detection_confidence=0.5, min_tracking_confidence=0.5, model_complexity=0
        )
        return ("solutions", pose, mp, cv2, np), None
    except (ImportError, OSError, AttributeError):
        return None, None

# Initialize pose (Tasks first, then solutions)
POSE_AVAILABLE = False
POSE_MODE = None
pose_tasks_detector = None
pose_sol = None
cv2 = np = mp = None

_detector, _ = _get_pose_detector_tasks()
if _detector is not None:
    try:
        import cv2
        import numpy as np
        import mediapipe as mp
        POSE_AVAILABLE = True
        POSE_MODE = "tasks"
        pose_tasks_detector = _detector
    except Exception:
        pass
if not POSE_AVAILABLE:
    sol = _get_pose_detector_solutions()
    if sol[0] is not None:
        _, pose_sol, mp, cv2, np = sol[0]
        POSE_AVAILABLE = True
        POSE_MODE = "solutions"

if not POSE_AVAILABLE and cv2 is None:
    try:
        import cv2
        import numpy as np
    except ImportError:
        cv2 = np = None

name_to_idx = {n: i for i, n in enumerate(POSE_LANDMARK_NAMES)}

def landmarks_from_tasks(detector, rgb_frame):
    h, w = rgb_frame.shape[:2]
    data = np.ascontiguousarray(rgb_frame)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=data)
    result = detector.detect(mp_image)
    if not result.pose_landmarks:
        return None, None
    pl = result.pose_landmarks[0]
    lm = {}
    for i, name in enumerate(POSE_LANDMARK_NAMES):
        if i < len(pl):
            l = pl[i]
            lm[name] = {"x": l.x, "y": l.y, "vis": getattr(l, "visibility", 1.0)}
    return lm, pl

def landmarks_from_solutions(pose_sol, rgb_frame):
    results = pose_sol.process(rgb_frame)
    if not results.pose_landmarks:
        return None, None
    pl = results.pose_landmarks.landmark
    lm = {}
    for i, name in enumerate(POSE_LANDMARK_NAMES):
        if i < len(pl):
            l = pl[i]
            lm[name] = {"x": l.x, "y": l.y, "vis": getattr(l, "visibility", 1.0)}
    return lm, pl

def process_frame_and_draw(img_bgr, coach, current_time):
    """Run pose, update coach, draw overlay on img_bgr. Returns same or annotated frame."""
    if cv2 is None or np is None:
        return img_bgr
    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    h, w = img_bgr.shape[:2]
    lm, pl = None, None
    if POSE_MODE == "tasks" and pose_tasks_detector is not None:
        lm, pl = landmarks_from_tasks(pose_tasks_detector, rgb)
    elif POSE_MODE == "solutions" and pose_sol is not None:
        lm, pl = landmarks_from_solutions(pose_sol, rgb)
    if lm and pl and coach:
        coach.process_form(lm, current_time)
        # Draw joint circles
        joint_colors = getattr(coach, "joint_colors", {})
        for name, color in joint_colors.items():
            idx = name_to_idx.get(name)
            if idx is not None and idx < len(pl):
                pt = pl[idx]
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
st.caption("Live camera — same as local: your device feed is analyzed in real time. Click **Start analysis** to begin.")

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
    st.session_state.analysis_started = False

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
# Expose to callback
LIVE_STATE["coach"] = coach
LIVE_STATE["analysis_active"] = st.session_state.analysis_started

if not POSE_AVAILABLE:
    st.warning("Pose analysis unavailable here (model or dependency). You still get live camera; enable pose for form feedback.")

# Live camera via WebRTC (same UX as main.py: continuous feed, overlay on video)
def video_frame_callback(frame):
    import av
    img = frame.to_ndarray(format="bgr24")
    active = LIVE_STATE.get("analysis_active", False)
    c = LIVE_STATE.get("coach")
    if active and c and POSE_AVAILABLE and cv2 is not None:
        img = process_frame_and_draw(img, c, time.time())
    elif not active and cv2 is not None:
        h, w = img.shape[:2]
        cv2.rectangle(img, (0, 0), (w, 50), (30, 30, 40), -1)
        cv2.putText(img, "Click 'Start analysis' in the sidebar", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
    return av.VideoFrame.from_ndarray(img, format="bgr24")

try:
    from streamlit_webrtc import webrtc_streamer
    webrtc_ctx = webrtc_streamer(
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
    st.info("Select an exercise, then click **Start analysis** in the sidebar. Your camera will run live and show reps/feedback on the video.")
