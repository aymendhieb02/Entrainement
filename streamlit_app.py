"""
Transformini Coach - Streamlit app.
Run: streamlit run streamlit_app.py
Deploy on share.streamlit.io (transformini-training-feedback).
Uses MediaPipe Tasks API (works with current mediapipe); falls back to solutions if available.
"""
import os
import time
import urllib.request
import streamlit as st
from biomechanics import (
    load_db, BiomechanicsCoach, prettify_exercise_name,
    get_categories_list, get_exercises_list, get_first_valid_exercise_key,
    is_exercise_valid_for_ui
)

# 33 pose landmark names in MediaPipe order (same as old solutions API) for coach compatibility
POSE_LANDMARK_NAMES = [
    "nose", "lefteyeinner", "lefteye", "lefteyeouter", "righteyeinner", "righteye", "righteyeouter",
    "leftear", "rightear", "mouthleft", "mouthright",
    "leftshoulder", "rightshoulder", "leftelbow", "rightelbow", "leftwrist", "rightwrist",
    "leftpinky", "rightpinky", "leftindex", "rightindex", "leftthumb", "rightthumb",
    "lefthip", "righthip", "leftknee", "rightknee", "leftankle", "rightankle",
    "leftheel", "rightheel", "leftfootindex", "rightfootindex",
]

def _get_pose_detector_tasks():
    """Use MediaPipe Tasks API (works with mediapipe 0.10.31+). Returns (detector, mp) or (None, None)."""
    try:
        import cv2
        import numpy as np
        import mediapipe as mp
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision
    except (ImportError, AttributeError):
        return None, None
    base_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(base_dir, "pose_landmarker.task")
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
    """Legacy: use mp.solutions.pose if available (mediapipe < 0.10.31)."""
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

# Prefer Tasks API (works on Streamlit Cloud with current mediapipe)
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

# ---- Page config and custom CSS (match index.html dark theme) ----
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
    [data-testid="stSidebar"] .stSelectbox label { color: rgba(255,255,255,0.9) !important; }
    [data-testid="stSidebar"] [data-baseweb="select"] { background: rgba(255,255,255,0.1) !important; color: white !important; border-color: rgba(255,255,255,0.2) !important; }
    .stButton > button { background: linear-gradient(45deg, #00f5ff, #00ff88) !important; color: #0f0c29 !important; font-weight: 700 !important; 
        border: none !important; border-radius: 10px !important; text-transform: uppercase !important; letter-spacing: 1px !important; 
        box-shadow: 0 4px 15px rgba(0,245,255,0.3) !important; }
    .stButton > button:hover { box-shadow: 0 6px 20px rgba(0,245,255,0.5) !important; transform: translateY(-2px) !important; }
    [data-testid="stMetricValue"] { color: #00f5ff !important; font-weight: 600 !important; }
    [data-testid="stMetricLabel"] { color: rgba(255,255,255,0.6) !important; }
    .info-card { background: rgba(255,255,255,0.08); padding: 1rem 1.25rem; border-radius: 12px; border: 1px solid rgba(255,255,255,0.1); 
        margin: 0.5rem 0; color: #00f5ff; font-weight: 600; }
    .stCameraInput { border-radius: 15px; overflow: hidden; box-shadow: 0 10px 40px rgba(0,0,0,0.5); }
    div[data-testid="stImage"] { border-radius: 15px; overflow: hidden; box-shadow: 0 10px 40px rgba(0,0,0,0.5); }
    .stProgress > div > div { background: linear-gradient(90deg, #00f5ff, #00ff88) !important; }
    p, span, label { color: rgba(255,255,255,0.9) !important; }
</style>
""", unsafe_allow_html=True)

st.title("Transformini Coach")
st.caption("Uses **your** camera (phone or PC) — capture a frame to get form feedback.")

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

coach = st.session_state.coach

# Show camera always so user can open it; if pose unavailable, show message but no analysis
if not POSE_AVAILABLE:
    st.warning("Pose analysis is unavailable on this environment. Camera will still open; install opencv-python-headless and a compatible mediapipe to enable analysis.")
else:
    POSE_MODE = "tasks" if pose_tasks_detector is not None else "solutions"

# Camera input (always shown)
img_bytes = st.camera_input("Use your device camera — take a photo to analyze your form")

def landmarks_from_tasks(detector, rgb_frame):
    """Run Tasks API and return lm dict + list of (x,y) for drawing, and raw landmarks for indices."""
    from mediapipe.tasks.python import vision
    h, w = rgb_frame.shape[:2]
    # MediaPipe Image from numpy (SRGB = RGB uint8); use contiguous array
    data = np.ascontiguousarray(rgb_frame)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=data)
    result = detector.detect(mp_image)
    if not result.pose_landmarks:
        return None, None, None
    pl = result.pose_landmarks[0]
    lm = {}
    for i, name in enumerate(POSE_LANDMARK_NAMES):
        if i < len(pl):
            l = pl[i]
            lm[name] = {"x": l.x, "y": l.y, "vis": getattr(l, "visibility", 1.0)}
    # For drawing: list of (x_px, y_px) in same order; and landmark list for index lookup
    points = [(int(lm[POSE_LANDMARK_NAMES[i]]["x"] * w), int(lm[POSE_LANDMARK_NAMES[i]]["y"] * h)) for i in range(min(len(POSE_LANDMARK_NAMES), len(pl)))]
    return lm, points, pl

def landmarks_from_solutions(pose_sol, rgb_frame):
    """Legacy solutions API: return lm dict + points for drawing + raw landmarks."""
    results = pose_sol.process(rgb_frame)
    if not results.pose_landmarks:
        return None, None, None
    pl = results.pose_landmarks.landmark
    lm = {}
    for i, name in enumerate(POSE_LANDMARK_NAMES):
        if i < len(pl):
            l = pl[i]
            lm[name] = {"x": l.x, "y": l.y, "vis": getattr(l, "visibility", 1.0)}
    h, w = rgb_frame.shape[:2]
    points = [(int(lm[POSE_LANDMARK_NAMES[i]]["x"] * w), int(lm[POSE_LANDMARK_NAMES[i]]["y"] * h)) for i in range(min(len(POSE_LANDMARK_NAMES), len(pl)))]
    return lm, points, pl

name_to_idx = {n: i for i, n in enumerate(POSE_LANDMARK_NAMES)}

if img_bytes and st.session_state.analysis_started and POSE_AVAILABLE and cv2 is not None:
    buf = img_bytes.getvalue()
    nparr = __import__("numpy").frombuffer(buf, dtype=np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is not None:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        if POSE_MODE == "tasks" and pose_tasks_detector is not None:
            lm, points, pl = landmarks_from_tasks(pose_tasks_detector, rgb)
        else:
            lm, points, pl = landmarks_from_solutions(pose_sol, rgb)
        if lm:
            coach.process_form(lm, time.time())
        # Draw joints on image
        from PIL import Image, ImageDraw
        h, w = frame.shape[:2]
        img_pil = Image.fromarray(rgb)
        draw = ImageDraw.Draw(img_pil)
        joint_colors = getattr(coach, "joint_colors", {})
        if pl is not None and joint_colors:
            for name, color in joint_colors.items():
                idx = name_to_idx.get(name)
                if idx is not None and idx < len(pl):
                    pt = pl[idx]
                    x, y = int(pt.x * w), int(pt.y * h)
                    fill = (0, 255, 136) if color == (0, 255, 0) else (255, 68, 68)
                    draw.ellipse([x - 12, y - 12, x + 12, y + 12], fill=fill, outline=(255, 255, 255))
        st.image(img_pil, use_container_width=True)

# Info panel (card style like index.html)
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
    st.info("Select an exercise and click **Start analysis** in the sidebar, then capture a frame.")
