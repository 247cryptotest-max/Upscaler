import os
import subprocess
import uuid
import shutil
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

app = FastAPI()

# Allow frontend (same origin or separate) – adjust if needed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, restrict to your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("outputs")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Cleanup old files after 1 hour (simple)
import threading
import time
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
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except:
        return False

@app.get("/check")
async def check_backend():
    return {"status": "active", "ffmpeg": check_ffmpeg()}

@app.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    # Validate file size (50MB)
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

    # Save uploaded file
    with open(input_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Upscale to 4K using Lanczos + unsharp mask
    cmd = [
        "ffmpeg", "-i", str(input_path),
        "-vf", "scale=3840:2160:flags=lanczos,unsharp=5:5:1.0:5:5:0.5",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
        "-y", str(output_path)
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)
    except subprocess.CalledProcessError as e:
        # Clean up and report error
        input_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)
        raise HTTPException(500, f"FFmpeg error: {e.stderr.decode()}")
    except subprocess.TimeoutExpired:
        input_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)
        raise HTTPException(500, "Processing timed out (5 min limit)")

    # Delete input file to save space
    input_path.unlink()

    return {"success": True, "download_id": input_id}

@app.get("/download/{download_id}")
async def download_video(download_id: str):
    # Find the output file (we know it ends with _4k.mp4)
    output_file = OUTPUT_DIR / f"{download_id}_4k.mp4"
    if not output_file.exists():
        raise HTTPException(404, "File not found or expired")
    return FileResponse(output_file, filename="upscaled_4k.mp4", media_type="video/mp4")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)
    
