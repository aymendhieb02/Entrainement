# Deploy on Streamlit Cloud (transformini-training-feedback)

## Run locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Open http://localhost:8501

## Deploy to Streamlit Cloud

1. Push this repo to **GitHub** (e.g. `main` branch).
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
3. **New app** → select your repo and branch.
4. **Main file path:** set to **`streamlit_app.py`** (not `main.py`). Using `main.py` causes crashes (Flask + mediapipe).
5. Deploy. Your app will be at: **transformini-training-feedback.streamlit.app**

Each visitor uses **their own** camera (phone or PC) via the in-app camera button; the app does not use the server’s camera.

## Requirements

- `streamlit_app.py` is the entry point (no Flask on Cloud).
- `opencv-python-headless` is used so the app runs without a display (no libGL).
- Data file `complete_exercise_biomechanics_database.json` must be in the repo.

## Local Flask (optional)

For local use with a physical camera and live feed:

```bash
python main.py
```

Then open the URL shown (e.g. http://127.0.0.1:5000). Streamlit Cloud uses the Streamlit app only.
