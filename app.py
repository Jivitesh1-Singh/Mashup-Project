from flask import Flask, render_template, request, flash
import os
import sys
import glob
import shutil
import zipfile
import smtplib
import re
import traceback
from email.message import EmailMessage
from dotenv import load_dotenv
from datetime import datetime
from time import sleep

from yt_dlp import YoutubeDL
from moviepy import VideoFileClip
from pydub import AudioSegment

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "your-secret-key-here")

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")

# ffmpeg setup - works both locally and on deployment
ffmpeg_path = os.getenv("FFMPEG_PATH", r"C:\Users\ASUS\OneDrive\Desktop\Mashup_Project\ffmpeg-8.0.1-essentials_build\ffmpeg-8.0.1-essentials_build\bin\ffmpeg.exe")

if os.path.exists(ffmpeg_path):
    ffmpeg_dir = os.path.dirname(ffmpeg_path)
    os.environ["IMAGEIO_FFMPEG_EXE"] = ffmpeg_path
    os.environ["FFMPEG_BINARY"] = ffmpeg_path
    os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
    AudioSegment.converter = ffmpeg_path
    AudioSegment.ffmpeg = ffmpeg_path
    AudioSegment.ffprobe = os.path.join(ffmpeg_dir, "ffprobe.exe")
else:
    # On deployment, use system ffmpeg
    AudioSegment.converter = shutil.which("ffmpeg") or "ffmpeg"
    AudioSegment.ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    AudioSegment.ffprobe = shutil.which("ffprobe") or "ffprobe"

def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def create_folders():
    for d in ("downloads", "audio", "trimmed", "output"):
        os.makedirs(d, exist_ok=True)

def download_videos(singer, num_videos):
    search_count = max(num_videos * 3, 30)
    query = f"ytsearch{search_count}:{singer}"
    
    ydl_opts = {
        "format": "best[ext=mp4]/best",
        "outtmpl": "downloads/%(id)s.%(ext)s",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 3,
        "socket_timeout": 10,
    }
    
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            entries = info.get("entries", []) or []
            selected = entries[:num_videos]
            urls = [e.get("webpage_url") or e.get("url") for e in selected]
            ydl.download(urls)
    except Exception:
        pass
    
    return sorted(glob.glob("downloads/*"))

def convert_to_audio():
    files = sorted(glob.glob("downloads/*"))
    for f in files:
        try:
            base = os.path.splitext(os.path.basename(f))[0]
            out_mp3 = os.path.join("audio", f"{base}.mp3")
            if os.path.exists(out_mp3):
                continue
            
            ext = os.path.splitext(f)[1].lower()
            if ext in (".m4a", ".mp3", ".webm", ".aac", ".wav", ".ogg"):
                AudioSegment.from_file(f).export(out_mp3, format="mp3")
            else:
                clip = VideoFileClip(f)
                clip.audio.write_audiofile(out_mp3, logger=None)
                clip.close()
            sleep(0.2)
        except Exception:
            pass

def trim_audio(duration_seconds):
    audios = sorted(glob.glob("audio/*.mp3"))
    for a in audios:
        try:
            base = os.path.basename(a)
            out_path = os.path.join("trimmed", base)
            if os.path.exists(out_path):
                continue
            sound = AudioSegment.from_file(a)
            trimmed = sound[:duration_seconds * 1000]
            trimmed.export(out_path, format="mp3")
        except Exception:
            pass

def merge_audio(output_filename):
    parts = sorted(glob.glob("trimmed/*.mp3"))
    if not parts:
        return False
    combined = AudioSegment.empty()
    for p in parts:
        try:
            combined += AudioSegment.from_file(p)
        except Exception:
            pass
    out_path = os.path.join("output", output_filename)
    combined.export(out_path, format="mp3")
    return True

def send_email(to_email, file_path):
    msg = EmailMessage()
    msg["Subject"] = "Your Mashup is Ready!"
    msg["From"] = EMAIL_USER
    msg["To"] = to_email
    msg.set_content("Hi! Your mashup has been created successfully. Please find it attached as a zip file.")

    zip_path = file_path.replace(".mp3", ".zip")
    with zipfile.ZipFile(zip_path, "w") as z:
        z.write(file_path, os.path.basename(file_path))

    with open(zip_path, "rb") as f:
        msg.add_attachment(f.read(), maintype="application", subtype="zip", 
                          filename=os.path.basename(zip_path))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_USER, EMAIL_PASS)
        smtp.send_message(msg)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        try:
            singer = request.form.get("singer", "").strip()
            num = request.form.get("num", "").strip()
            duration = request.form.get("duration", "").strip()
            email = request.form.get("email", "").strip()
            
            if not all([singer, num, duration, email]):
                return render_template("index.html", error="All fields are required!")
            
            if not validate_email(email):
                return render_template("index.html", error="Please enter a valid email address!")
            
            try:
                num_videos = int(num)
                duration_sec = int(duration)
            except ValueError:
                return render_template("index.html", error="Number of videos and duration must be integers!")
            
            if num_videos <= 10:
                return render_template("index.html", error="Number of videos must be greater than 10!")
            
            if duration_sec <= 20:
                return render_template("index.html", error="Duration must be greater than 20 seconds!")
            
            create_folders()
            output_file = f"mashup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
            
            download_videos(singer, num_videos)
            convert_to_audio()
            trim_audio(duration_sec)
            merge_audio(output_file)
            
            file_path = os.path.join("output", output_file)
            if os.path.exists(file_path):
                send_email(email, file_path)
                return render_template("index.html", success="Mashup created and sent to your email!")
            else:
                return render_template("index.html", error="Failed to create mashup. Please try again.")
                
        except Exception as e:
            return render_template("index.html", error=f"An error occurred: {str(e)}")
    
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)
