import os
import glob
import random
import datetime
import subprocess
import requests
import numpy as np
import librosa
from PIL import Image, ImageEnhance, ImageFilter
from scipy.io.wavfile import write as wav_write
from icrawler.builtin import BingImageCrawler
from moviepy.editor import ImageClip, AudioFileClip, ColorClip, CompositeVideoClip, concatenate_videoclips

GITHUB_USER = "nishantha31-eng"
REPO_NAME = "insta-auto-edits"

# Queries tuned for clean, text-free photography
TOPICS = [
    {"query": "JDM sports car night photography clean wallpaper", "caption": "Late night JDM vibes. 🏎️💨 #cars #jdm #carsofinstagram #reels"},
    {"query": "cricket stadium match photography action shot", "caption": "Pure cricket adrenaline. 🏏🔥 #cricket #cricketlovers #reels"},
    {"query": "UEFA Champions League soccer match photography", "caption": "Under the stadium lights. ⚽✨ #football #soccer #championsleague #reels"},
    {"query": "Lionel Messi Cristiano Ronaldo match photography", "caption": "Pure football greatness. ⚽🐐 #football #soccer #messi #ronaldo"}
]

PHONK_QUERIES = [
    "brazilian phonk",
    "drift phonk",
    "aggressive phonk edit",
    "trending phonk tik tok"
]

def has_text_or_watermark(img):
    # Checks high-contrast sharp edges in top/bottom/center bands where watermarks & captions sit
    gray = img.convert("L").resize((270, 480))
    edges = np.array(gray.filter(ImageFilter.FIND_EDGES), dtype=np.float32)
    top_band = edges[:90, :].mean()
    bottom_band = edges[-90:, :].mean()
    center_band = edges[180:300, :].mean()
    # Reject images with heavy text/banners at top, bottom, or across the middle
    if top_band > 38 or bottom_band > 38 or center_band > 45:
        return True
    return False

def add_cinematic_vignette(img):
    w, h = img.size
    x = np.linspace(-1, 1, w)
    y = np.linspace(-1, 1, h)
    X, Y = np.meshgrid(x, y)
    radius = np.sqrt(X**2 + Y**2)
    mask = np.clip(1.0 - 0.35 * (radius**1.8), 0.55, 1.0)
    arr = np.array(img, dtype=np.float32) * mask[:, :, np.newaxis]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

def generate_fallback_beat(output_audio="bg_track.wav", duration=15, bpm=132):
    sr = 44100
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    beat_interval = 60.0 / bpm
    beat_pos = (t % beat_interval) / beat_interval
    kick = np.sin(2 * np.pi * (55 + 95 * np.exp(-beat_pos * 18)) * t) * np.exp(-beat_pos * 8)
    hat = np.random.uniform(-0.15, 0.15, len(t)) * np.exp(-((t % (beat_interval / 2)) / (beat_interval / 2)) * 25)
    audio = np.clip(kick * 0.85 + hat, -1.0, 1.0)
    wav_write(output_audio, sr, (audio * 32767).astype(np.int16))
    return output_audio

def fetch_auto_audio(output_audio="bg_track.mp3"):
    try:
        query = random.choice(PHONK_QUERIES)
        pick = random.randint(1, 8)
        cmd = [
            "yt-dlp",
            f"scsearch10:{query}",
            "--playlist-items", str(pick),
            "-x", "--audio-format", "mp3",
            "--match-filter", "duration >= 25 & duration <= 300",
            "-o", output_audio
        ]
        subprocess.run(cmd, check=True, timeout=45)
        if os.path.exists(output_audio) and os.path.getsize(output_audio) > 100_000:
            return output_audio
    except Exception as e:
        print("SoundCloud fetch skipped:", e)

    try:
        res = requests.get(
            "https://audius.co",
            params={"query": random.choice(PHONK_QUERIES), "app_name": "AutoReelsBot"},
            timeout=15
        ).json()
        tracks = res.get("data", [])
        if tracks:
            chosen = random.choice(tracks[:10])
            stream_url = f"https://audius.co{chosen['id']}/stream?app_name=AutoReelsBot"
            dl = requests.get(stream_url, timeout=25)
            if dl.status_code == 200 and len(dl.content) > 100_000:
                with open(output_audio, "wb") as f:
                    f.write(dl.content)
                return output_audio
    except Exception as e:
        print("Audius fetch skipped:", e)

    return generate_fallback_beat("bg_track.wav")

def download_images(query, count=9):
    os.makedirs("raw_imgs", exist_ok=True)
    os.makedirs("imgs", exist_ok=True)
    crawler = BingImageCrawler(storage={"root_dir": "raw_imgs"})
    # Negative keywords block watermarked stock agencies & poster/meme text
    clean_query = f"{query} -watermark -shutterstock -gettyimages -alamy -istock -quote -poster"
    crawler.crawl(keyword=clean_query, max_num=35)

    paths = []
    for raw_path in glob.glob("raw_imgs/*"):
        if len(paths) >= count:
            break
        try:
            img = Image.open(raw_path).convert("RGB")
            if img.width >= 600 and img.height >= 600:
                if has_text_or_watermark(img):
                    continue
                target_ratio = 1080 / 1920
                img_ratio = img.width / img.height
                if img_ratio > target_ratio:
                    new_w = int(img.height * target_ratio)
                    left = (img.width - new_w) // 2
                    img = img.crop((left, 0, left + new_w, img.height))
                else:
                    new_h = int(img.width / target_ratio)
                    top = (img.height - new_h) // 2
                    img = img.crop((0, top, img.width, top + new_h))
                img = img.resize((1080, 1920), Image.Resampling.LANCZOS)
                img = ImageEnhance.Contrast(img).enhance(1.15)
                img = ImageEnhance.Color(img).enhance(1.18)
                img = add_cinematic_vignette(img)
                out_path = f"imgs/img_{len(paths)}.jpg"
                img.save(out_path, quality=95)
                paths.append(out_path)
        except Exception:
            continue
    return paths

def build_beat_synced_video(image_paths, audio_path, output_path="latest_reel.mp4"):
    total_dur = AudioFileClip(audio_path).duration
    start_offset = 15.0 if total_dur > 35.0 else 0.0

    y, sr = librosa.load(audio_path, offset=start_offset, duration=15)
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)

    cuts = [0.0]
    for b in beat_times[1::2]:
        if b <= 14.2 and len(cuts) < len(image_paths):
            cuts.append(float(b))
    cuts.append(min(15.0, cuts[-1] + 1.8))

    clips = []
    for idx, img_path in enumerate(image_paths[:len(cuts)-1]):
        duration = max(0.55, cuts[idx+1] - cuts[idx])
        # CapCut-style exponential punch-in / punch-out + impact camera shake on first 0.2s
        if idx % 2 == 0:
            base_clip = (ImageClip(img_path)
                         .set_duration(duration)
                         .resize(lambda t, d=duration: 1.04 + 0.14 * ((t / d) ** 0.6))
                         .set_position(lambda t: ("center", int(18 * np.sin(t * 45) * np.exp(-t * 14)))))
        else:
            base_clip = (ImageClip(img_path)
                         .set_duration(duration)
                         .resize(lambda t, d=duration: 1.18 - 0.14 * ((t / d) ** 0.6))
                         .set_position(lambda t: (int(18 * np.cos(t * 45) * np.exp(-t * 14)), "center")))

        flash = (ColorClip(size=(1080, 1920), color=(255, 255, 255))
                 .set_duration(min(0.09, duration * 0.3))
                 .set_opacity(0.55))
        comp = CompositeVideoClip([base_clip, flash], size=(1080, 1920)).set_duration(duration)
        clips.append(comp)

    video = concatenate_videoclips(clips, method="compose")
    audio = AudioFileClip(audio_path).subclip(start_offset, start_offset + video.duration)
    video = video.set_audio(audio)
    video.write_videofile(output_path, fps=30, codec="libx264", audio_codec="aac")
    return output_path

def update_rss_feed(caption):
    now = datetime.datetime.now(datetime.timezone.utc)
    pub_date = now.strftime("%a, %d %b %Y %H:%M:%S +0000")
    unique_id = now.strftime("%Y%m%d%H%M%S")
    video_url = f"https://{GITHUB_USER}.github.io/{REPO_NAME}/latest_reel.mp4?v={unique_id}"

    rss_content = f"""<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
<channel>
  <title>Auto Sports and Car Edits</title>
  <link>https://{GITHUB_USER}.github.io/{REPO_NAME}/</link>
  <description>Automated daily edits</description>
  <item>
    <title>{caption}</title>
    <link>{video_url}</link>
    <guid>{unique_id}</guid>
    <pubDate>{pub_date}</pubDate>
    <description>{caption}</description>
    <enclosure url="{video_url}" type="video/mp4" />
  </item>
</channel>
</rss>
"""
    with open("feed.xml", "w", encoding="utf-8") as f:
        f.write(rss_content)

if __name__ == "__main__":
    choice = random.choice(TOPICS)
    images = download_images(choice["query"], count=9)
    chosen_audio = fetch_auto_audio("bg_track.mp3")
    build_beat_synced_video(images, chosen_audio, "latest_reel.mp4")
    update_rss_feed(choice["caption"])
