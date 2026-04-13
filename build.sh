#!/bin/bash
# Install FFmpeg on Render
apt-get update
apt-get install -y ffmpeg
pip install -r requirements.txt
