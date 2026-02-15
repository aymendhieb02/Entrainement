#!/bin/bash
# Force opencv-python-headless so Railway has no libGL. Run this as Railway build command.
pip install -r requirements.txt
pip uninstall -y opencv-python 2>/dev/null || true
pip install --force-reinstall --no-deps opencv-python-headless==4.9.0.80
