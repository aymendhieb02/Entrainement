FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install OS dependencies needed by mediapipe, OpenCV and streamlit-webrtc
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       ffmpeg \
       libglib2.0-0 \
       libsm6 \
       libxrender1 \
       libxext6 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt ./
RUN python -m pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy app sources
COPY . /app

EXPOSE 8501

CMD ["streamlit", "run", "streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
