import os
import uuid
import subprocess
import shutil
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, request, jsonify, send_file, render_template, url_for
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Configuration
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max upload
BASE_DIR = Path('/tmp/4k_upscaler')
UPLOAD_FOLDER = BASE_DIR / 'uploads'
OUTPUT_FOLDER = BASE_DIR / 'outputs'
BASE_DIR.mkdir(exist_ok=True, parents=True)
UPLOAD_FOLDER.mkdir(exist_ok=True)
OUTPUT_FOLDER.mkdir(exist_ok=True)

# Track files with their creation time for cleanup
file_tracker = {}
CLEANUP_INTERVAL_SECONDS = 3600  # 1 hour
FILE_LIFETIME_SECONDS = 3600     # 1 hour

def cleanup_old_files():
    """Remove files older than FILE_LIFETIME_SECONDS"""
    while True:
        try:
            now = time.time()
            to_delete = []
            for file_id, data in list(file_tracker.items()):
                if now - data['timestamp'] > FILE_LIFETIME_SECONDS:
                    to_delete.append(file_id)
            for file_id in to_delete:
                data = file_tracker.pop(file_id, None)
                if data:
                    for file_path in [data['input_path'], data['output_path']]:
                        try:
                            if os.path.exists(file_path):
                                os.unlink(file_path)
                        except Exception:
                            pass
        except Exception:
            pass
        time.sleep(CLEANUP_INTERVAL_SECONDS)

# Start cleanup thread
cleanup_thread = threading.Thread(target=cleanup_old_files, daemon=True)
cleanup_thread.start()

def is_ffmpeg_available():
    """Check if FFmpeg is installed and accessible"""
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False

# Replace the @app.route('/') function with this:

@app.route('/')
def index():
    with open('index.html', 'r') as f:
        return f.read()

@app.route('/check', methods=['GET'])
def check_backend():
    """Endpoint for the UI to check if backend is awake and FFmpeg is ready"""
    ffmpeg_ok = is_ffmpeg_available()
    return jsonify({
        'status': 'active',
        'ffmpeg': ffmpeg_ok,
        'message': 'Backend is ready' if ffmpeg_ok else 'FFmpeg is missing'
    })

@app.route('/upload', methods=['POST'])
def upload_video():
    """Upload video, process with FFmpeg, return download ID"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Empty filename'}), 400
    
    if not file.filename.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm')):
        return jsonify({'error': 'Unsupported file format. Please upload MP4, MOV, AVI, MKV, or WEBM.'}), 400
    
    # Generate unique IDs and paths
    file_id = str(uuid.uuid4())
    input_ext = Path(secure_filename(file.filename)).suffix or '.mp4'
    input_path = UPLOAD_FOLDER / f"{file_id}_input{input_ext}"
    output_path = OUTPUT_FOLDER / f"{file_id}_4k.mp4"
    
    # Save uploaded file
    file.save(input_path)
    
    # FFmpeg filter: Lanczos scale to 4K preserving aspect ratio + pad + unsharp
    vf_filter = (
        "scale=3840:2160:force_original_aspect_ratio=1,"
        "pad=3840:2160:(ow-iw)/2:(oh-ih)/2,"
        "unsharp=5:5:0.8:5:5:0.0"
    )
    
    # Build FFmpeg command
    cmd = [
        'ffmpeg', '-i', str(input_path),
        '-vf', vf_filter,
        '-preset', 'superfast',
        '-pix_fmt', 'yuv420p',
        '-c:v', 'libx264',
        '-c:a', 'aac',
        '-b:a', '128k',
        '-threads', '2',
        '-y',  # overwrite output if exists
        str(output_path)
    ]
    
    try:
        # Run FFmpeg with timeout (10 minutes max)
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        # Clean up input and any partial output
        if input_path.exists():
            os.unlink(input_path)
        if output_path.exists():
            os.unlink(output_path)
        return jsonify({'error': 'Processing took too long (over 10 minutes). Please try a shorter video.'}), 500
    except subprocess.CalledProcessError as e:
        # Clean up on error
        if input_path.exists():
            os.unlink(input_path)
        if output_path.exists():
            os.unlink(output_path)
        app.logger.error(f"FFmpeg error: {e.stderr}")
        return jsonify({'error': f'FFmpeg processing failed: {e.stderr[:200]}'}), 500
    
    # Store file info for download and later cleanup
    file_tracker[file_id] = {
        'input_path': str(input_path),
        'output_path': str(output_path),
        'timestamp': time.time()
    }
    
    return jsonify({
        'success': True,
        'download_id': file_id,
        'message': 'Video upscaled to 4K successfully!'
    })

@app.route('/download/<download_id>')
def download_file(download_id):
    """Download the processed 4K video and delete temp files"""
    file_info = file_tracker.get(download_id)
    if not file_info:
        return jsonify({'error': 'Download ID not found or expired'}), 404
    
    output_path = file_info['output_path']
    if not os.path.exists(output_path):
        return jsonify({'error': 'Processed file no longer exists'}), 404
    
    # Send file and then delete both input and output
    try:
        response = send_file(
            output_path,
            as_attachment=True,
            download_name=f"4k_upscaled_{download_id}.mp4",
            mimetype='video/mp4'
        )
        # Delete files after sending
        if os.path.exists(file_info['input_path']):
            os.unlink(file_info['input_path'])
        if os.path.exists(output_path):
            os.unlink(output_path)
        # Remove from tracker
        file_tracker.pop(download_id, None)
        return response
    except Exception as e:
        return jsonify({'error': f'Download failed: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
    
