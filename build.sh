#!/bin/bash
# Install FFmpeg using static binary (no apt required)
set -e

echo "📦 Downloading static FFmpeg..."
FFMPEG_URL="https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
curl -L $FFMPEG_URL -o ffmpeg.tar.xz

echo "📂 Extracting..."
tar -xf ffmpeg.tar.xz

echo "🚚 Moving to /usr/local/bin..."
mv ffmpeg-*-amd64-static/ffmpeg /usr/local/bin/
mv ffmpeg-*-amd64-static/ffprobe /usr/local/bin/
chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe

echo "🧹 Cleaning up..."
rm -rf ffmpeg.tar.xz ffmpeg-*-amd64-static

echo "🐍 Installing Python dependencies..."
pip install -r requirements.txt

echo "✅ Build complete"
