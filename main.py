import os
import subprocess
import uuid
import shutil
from flask import Flask, request, jsonify, send_file, render_template_string, after_this_request
from werkzeug.utils import secure_filename
import tempfile
import threading
import time
import requests

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max upload (reduced from 200MB for free tier)
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()

ALLOWED_EXTENSIONS = {'mp4', 'mov', 'avi', 'mkv', 'webm'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def run_ffmpeg(input_path, output_path):
    """Run FFmpeg with Lanczos scaling to 4K + unsharp filter"""
    cmd = [
        'ffmpeg',
        '-i', input_path,
        '-vf', 'scale=3840:2160:flags=lanczos,unsharp=5:5:0.8:5:5:0.0',
        '-preset', 'superfast',
        '-pix_fmt', 'yuv420p',
        '-c:v', 'libx264',
        '-crf', '23',
        '-c:a', 'aac',
        '-b:a', '128k',
        '-movflags', '+faststart',
        output_path,
        '-y'  # Overwrite output file if exists
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise Exception(f"FFmpeg error: {result.stderr}")
    return True

@app.route('/')
def index():
    with open('index.html', 'r') as f:
        return render_template_string(f.read())

@app.route('/check', methods=['GET'])
def check_status():
    """Simple endpoint to check if backend is awake"""
    return jsonify({'status': 'active', 'message': '✅ Backend is active'}), 200

@app.route('/upload', methods=['POST'])
def upload_video():
    if 'video' not in request.files:
        return jsonify({'error': 'No video file provided'}), 400
    
    file = request.files['video']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed. Use MP4, MOV, AVI, MKV, or WEBM'}), 400
    
    # Generate unique filenames
    original_ext = file.filename.rsplit('.', 1)[1].lower()
    input_filename = f"input_{uuid.uuid4().hex}.{original_ext}"
    output_filename = f"output_{uuid.uuid4().hex}.mp4"
    input_path = os.path.join(app.config['UPLOAD_FOLDER'], input_filename)
    output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
    
    try:
        # Save uploaded file
        file.save(input_path)
        
        # Run FFmpeg conversion
        run_ffmpeg(input_path, output_path)
        
        # Send file and clean up after
        @after_this_request
        def cleanup(response):
            try:
                if os.path.exists(input_path):
                    os.remove(input_path)
                if os.path.exists(output_path):
                    os.remove(output_path)
            except Exception as e:
                app.logger.error(f"Cleanup error: {e}")
            return response
        
        return send_file(
            output_path,
            as_attachment=True,
            download_name=f"4k_upscaled_{uuid.uuid4().hex}.mp4",
            mimetype='video/mp4'
        )
    
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Processing took too long (>10 minutes)'}), 500
    except Exception as e:
        # Clean up on error
        if os.path.exists(input_path):
            os.remove(input_path)
        if os.path.exists(output_path):
            os.remove(output_path)
        return jsonify({'error': f'Processing failed: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
    
