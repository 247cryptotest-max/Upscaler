#!/bin/bash
set -e

echo "📦 Downloading static FFmpeg..."
FFMPEG_URL="https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
curl -L $FFMPEG_URL -o ffmpeg.tar.xz

echo "📂 Extracting..."
tar -xf ffmpeg.tar.xz

echo "🚚 Moving to $HOME/bin..."
mkdir -p $HOME/bin
mv ffmpeg-*-amd64-static/ffmpeg $HOME/bin/
mv ffmpeg-*-amd64-static/ffprobe $HOME/bin/
chmod +x $HOME/bin/ffmpeg $HOME/bin/ffprobe

echo "🧹 Cleaning up..."
rm -rf ffmpeg.tar.xz ffmpeg-*-amd64-static

# Add $HOME/bin to PATH for this build and runtime
export PATH="$HOME/bin:$PATH"
echo "export PATH=\"\$HOME/bin:\$PATH\"" >> $HOME/.profile

echo "🐍 Installing Python dependencies..."
pip install -r requirements.txt

echo "✅ Build complete"
