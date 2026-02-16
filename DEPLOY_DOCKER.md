Deploying the Transformini Coach app with Docker

Quick steps (build and run locally):

1. Build the image (from project root):

```
docker build -t transformini-coach:latest .
```

2. Run the container and expose Streamlit on port 8501:

```
docker run --rm -p 8501:8501 transformini-coach:latest
```

When the container starts, open http://localhost:8501 and confirm the Debug sidebar shows:

- `mediapipe: 0.10.30`
- `cv2: 4.9.0`
- `numpy: 1.26.4`

Deploying to a host/service:

- Streamlit Cloud does not currently support custom Docker images. Use a provider that accepts Docker (Render, Fly.io, Railway, DigitalOcean App Platform, or a VM) to ensure the correct Python runtime and native wheels for MediaPipe.
- On these platforms you can either push the Dockerfile or use their Docker image deployment flow.

Notes:
- The Docker image uses `python:3.11-slim` to match MediaPipe's supported wheels. This avoids import-time issues where `mp.solutions` is missing under unsupported Python versions.
- If you prefer, I can add platform-specific deployment examples (Render/Fly) or a GitHub Actions workflow to build and push the image.
