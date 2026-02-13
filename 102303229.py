import os
import sys
import glob
import shutil
import traceback
from datetime import datetime
from time import sleep

ffmpeg_path = r"C:\Users\ASUS\OneDrive\Desktop\Mashup_Project\ffmpeg-8.0.1-essentials_build\ffmpeg-8.0.1-essentials_build\bin\ffmpeg.exe"

# setup ffmpeg for other libraries
ffmpeg_dir = os.path.dirname(ffmpeg_path)
os.environ["IMAGEIO_FFMPEG_EXE"] = ffmpeg_path
os.environ["FFMPEG_BINARY"] = ffmpeg_path
os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")

try:
    from yt_dlp import YoutubeDL
    from moviepy.editor import VideoFileClip
    from pydub import AudioSegment
except Exception:
    print("Missing required packages. Run:\n  pip install yt-dlp moviepy pydub")
    raise

AudioSegment.converter = ffmpeg_path
AudioSegment.ffmpeg = ffmpeg_path
AudioSegment.ffprobe = os.path.join(ffmpeg_dir, "ffprobe.exe")

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def create_folders():
    for d in ("downloads", "audio", "trimmed", "output"):
        os.makedirs(d, exist_ok=True)

def clear_folder(folder):
    for p in glob.glob(os.path.join(folder, "*")):
        try:
            if os.path.isfile(p):
                os.remove(p)
            else:
                shutil.rmtree(p)
        except Exception:
            pass

def download_videos(singer, num_videos, max_duration=600, extra_search_multiplier=3):
    log(f"Starting download: need {num_videos} items for '{singer}' (prefer <= {max_duration}s each)")
    search_count = max(num_videos * extra_search_multiplier, 30)
    query = f"ytsearch{search_count}:{singer}"

    ydl_info_opts = {"quiet": True, "no_warnings": True}
    ydl_download_opts = {
        "format": "best[ext=mp4]/best",
        "outtmpl": "downloads/%(id)s.%(ext)s",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 3,
        "socket_timeout": 10,
    }

    try:
        with YoutubeDL(ydl_info_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            entries = info.get("entries", []) or []
    except Exception:
        log("Failed to fetch search results. Will attempt direct download fallback.")
        entries = []

    selected = []
    for e in entries:
        if len(selected) >= num_videos:
            break
        dur = e.get("duration")
        if dur is None or (isinstance(dur, (int, float)) and dur <= max_duration):
            selected.append(e)

    if len(selected) < num_videos:
        log(f"Only found {len(selected)} short items. Relaxing max_duration to 1800s (30min).")
        for e in entries:
            if len(selected) >= num_videos:
                break
            if e in selected:
                continue
            dur = e.get("duration")
            if dur is None or dur <= 1800:
                selected.append(e)

    if len(selected) < num_videos:
        log("Still not enough filtered items; taking top search results (may include long videos).")
        for e in entries:
            if len(selected) >= num_videos:
                break
            if e not in selected:
                selected.append(e)

    if not selected:
        log("No search metadata available; attempting direct ytsearch download (yt-dlp internal).")
        try:
            with YoutubeDL(ydl_download_opts) as ydl:
                ydl.download([f"ytsearch{num_videos}:{singer}"])
            downloaded = sorted(glob.glob("downloads/*"))
            log(f"Direct download finished: {len(downloaded)} items.")
            return downloaded
        except Exception:
            log("Direct download failed. Aborting.")
            traceback.print_exc()
            return []

    urls = [e.get("webpage_url") or e.get("url") for e in selected]
    log(f"Downloading {len(urls)} selected items (audio-only format). This may take a while...")
    try:
        with YoutubeDL(ydl_download_opts) as ydl:
            ydl.download(urls)
    except Exception:
        log("Warning: some downloads failed during download step.")
        traceback.print_exc()

    downloaded = sorted(glob.glob("downloads/*"))
    log(f"Downloaded {len(downloaded)} items (audio or short video files).")
    return downloaded

def convert_to_audio():
    log("Converting downloads to mp3 in audio/ ...")
    files = sorted(glob.glob("downloads/*"))
    converted = 0
    for f in files:
        try:
            base = os.path.splitext(os.path.basename(f))[0]
            out_mp3 = os.path.join("audio", f"{base}.mp3")
            if os.path.exists(out_mp3):
                converted += 1
                continue

            ext = os.path.splitext(f)[1].lower()
            if ext in (".m4a", ".mp3", ".webm", ".aac", ".wav", ".ogg", ".flac"):
                AudioSegment.from_file(f).export(out_mp3, format="mp3")
            else:
                clip = VideoFileClip(f)
                clip.audio.write_audiofile(out_mp3, logger=None)
                clip.close()

            converted += 1
            sleep(0.2)
        except Exception:
            log(f"Failed to convert {f} → skipping.")
            traceback.print_exc()
    log(f"Conversion finished. Converted {converted} files.")
    return converted

def trim_audio_each(duration_seconds):
    log(f"Trimming each audio to {duration_seconds} seconds (trimmed/)...")
    audios = sorted(glob.glob("audio/*.mp3"))
    created = 0
    for a in audios:
        try:
            base = os.path.basename(a)
            out_path = os.path.join("trimmed", base)
            if os.path.exists(out_path):
                created += 1
                continue

            sound = AudioSegment.from_file(a)
            trimmed = sound[: duration_seconds * 1000]
            trimmed.export(out_path, format="mp3")
            created += 1
        except Exception:
            log(f"Failed to trim {a} (skip).")
            traceback.print_exc()
    log(f"Trimming done. {created} trimmed files created.")
    return created

def merge_all(output_filename):
    log("Merging trimmed files into final mashup...")
    parts = sorted(glob.glob("trimmed/*.mp3"))
    if not parts:
        log("No parts found to merge.")
        return False
    combined = AudioSegment.empty()
    for p in parts:
        try:
            seg = AudioSegment.from_file(p)
            combined += seg
        except Exception:
            log(f"Skipping corrupted part: {p}")
            traceback.print_exc()

    out_path = os.path.join("output", output_filename)
    combined.export(out_path, format="mp3")
    log(f"Mashup saved to {out_path}")
    return True

def validate_and_run(argv):
    if len(argv) != 5:
        print("Usage: python <program.py> \"<SingerName>\" <NumberOfVideos> <AudioDurationSec> <OutputFile.mp3>")
        sys.exit(1)

    singer = argv[1].strip()
    try:
        num_videos = int(argv[2])
        duration = int(argv[3])
    except ValueError:
        print("NumberOfVideos and AudioDuration must be integers.")
        sys.exit(1)

    out_name = argv[4].strip()
    if not out_name.lower().endswith(".mp3"):
        out_name += ".mp3"

    if num_videos <= 10:
        print("Error: NumberOfVideos must be greater than 10.")
        sys.exit(1)
    if duration <= 20:
        print("Error: AudioDuration must be greater than 20 seconds.")
        sys.exit(1)

    create_folders()

    downloaded = download_videos(singer, num_videos, max_duration=600)
    if not downloaded:
        log("No files downloaded. Exiting.")
        sys.exit(1)

    conv = convert_to_audio()
    if conv == 0:
        log("No files converted to mp3. Exiting.")
        sys.exit(1)

    trimmed = trim_audio_each(duration)
    if trimmed == 0:
        log("No trimmed files created. Exiting.")
        sys.exit(1)

    ok = merge_all(out_name)
    if not ok:
        log("Merge failed. Exiting.")
        sys.exit(1)

    log("Done — check output/ for the mashup file.")

if __name__ == "__main__":
    try:
        validate_and_run(sys.argv)
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    except Exception:
        print("Fatal error:")
        traceback.print_exc()
