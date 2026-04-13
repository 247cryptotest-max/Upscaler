import os
import subprocess
import uuid
import shutil
import stat
import threading
import time
import resource  # for memory limiting
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("outputs")
STATIC_DIR = Path("static")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        return HTMLResponse("<h1>index.html not found in static/ folder</h1>", status_code=404)
    with open(index_path, "r", encoding="utf-8") as f:
        return f.read()

# Find ffmpeg binary
FFMPEG_PATH = shutil.which("ffmpeg")
if not FFMPEG_PATH:
    local_ffmpeg = Path("ffmpeg")
    if local_ffmpeg.exists():
        FFMPEG_PATH = str(local_ffmpeg)
        st = os.stat(FFMPEG_PATH)
        os.chmod(FFMPEG_PATH, st.st_mode | stat.S_IEXEC)
    else:
        FFMPEG_PATH = "ffmpeg"  # will fail, but let it

def cleanup_old_files():
    while True:
        time.sleep(3600)
        for d in [UPLOAD_DIR, OUTPUT_DIR]:
            for f in d.glob("*"):
                if time.time() - f.stat().st_mtime > 3600:
                    f.unlink()
threading.Thread(target=cleanup_old_files, daemon=True).start()

def check_ffmpeg():
    try:
        subprocess.run([FFMPEG_PATH, "-version"], capture_output=True, check=True)
        return True
    except:
        return False

@app.get("/check")
async def check_backend():
    return {"status": "active", "ffmpeg": check_ffmpeg()}

@app.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    # Optional: limit memory for this process (Linux/macOS only)
    try:
        resource.setrlimit(resource.RLIMIT_AS, (400 * 1024 * 1024, 400 * 1024 * 1024))
    except (AttributeError, resource.error):
        pass  # ignore on Windows or if not permitted

    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)
    if size > 50 * 1024 * 1024:
        raise HTTPException(400, "File too large (max 50MB)")

    ext = os.path.splitext(file.filename)[1]
    if ext.lower() not in [".mp4", ".mov", ".avi", ".mkv", ".webm"]:
        raise HTTPException(400, "Unsupported video format")

    input_id = str(uuid.uuid4())
    input_path = UPLOAD_DIR / f"{input_id}{ext}"
    output_path = OUTPUT_DIR / f"{input_id}_4k.mp4"

    with open(input_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Memory-optimized command: 1080p, single thread, ultrafast preset
    cmd = [
        FFMPEG_PATH, "-i", str(input_path),
        "-threads", "1",
        "-vf", "scale=1920:1080:flags=lanczos,unsharp=5:5:1.0:5:5:0.5",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
        "-y", str(output_path)
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)
    except subprocess.CalledProcessError as e:
        input_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)
        raise HTTPException(500, f"FFmpeg error: {e.stderr.decode()}")
    except subprocess.TimeoutExpired:
        input_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)
        raise HTTPException(500, "Processing timed out (5 min limit)")

    input_path.unlink()
    return {"success": True, "download_id": input_id}

@app.get("/download/{download_id}")
async def download_video(download_id: str):
    output_file = OUTPUT_DIR / f"{download_id}_4k.mp4"
    if not output_file.exists():
        raise HTTPException(404, "File not found or expired")
    return FileResponse(output_file, filename="upscaled_4k.mp4", media_type="video/mp4")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)
    
